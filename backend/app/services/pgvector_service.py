import logging
import json
from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import engine

from ..core.config import settings
from ..core.exceptions import VectorDBError

logger = logging.getLogger(__name__)

# DDL executed once on startup via ensure_table().
# search_vector is populated automatically by a trigger so callers
# never have to touch it directly.
_DDL_COMMANDS = [
    "CREATE EXTENSION IF NOT EXISTS vector;",
    
    """
    CREATE TABLE IF NOT EXISTS document_chunks (
        chunk_id      TEXT        PRIMARY KEY,
        doc_id        UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        text_chunk    TEXT        NOT NULL,
        embedding     halfvec(3072),
        search_vector tsvector,
        chunk_number  INTEGER     DEFAULT 0,
        filename      TEXT        DEFAULT '',
        source_type   TEXT        DEFAULT '',
        created_at    TIMESTAMPTZ DEFAULT now()
    );
    """,
    
    """
    CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
        ON document_chunks
        USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """,
    
    """
    CREATE INDEX IF NOT EXISTS document_chunks_search_vector_idx
        ON document_chunks
        USING GIN (search_vector);
    """,
    
    """
    CREATE INDEX IF NOT EXISTS document_chunks_doc_id_idx
        ON document_chunks (doc_id);
    """,
    
    """
    CREATE OR REPLACE FUNCTION _update_chunk_search_vector()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.search_vector := to_tsvector('english', NEW.text_chunk);
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """,
    
    "DROP TRIGGER IF EXISTS trg_chunk_search_vector ON document_chunks;",
    
    """
    CREATE TRIGGER trg_chunk_search_vector
        BEFORE INSERT OR UPDATE OF text_chunk
        ON document_chunks
        FOR EACH ROW
        EXECUTE FUNCTION _update_chunk_search_vector();
    """
]

# Hybrid query: dense CTE + sparse CTE fused with RRF (k=60).
# Sparse leg uses websearch_to_tsquery so raw user input is safe.
# Falls back to dense-only when the sparse query produces NULL
# (e.g. all stop-words, empty string, or no tsquery tokens).
_HYBRID_QUERY = """
WITH
dense AS (
    SELECT chunk_id, text_chunk, doc_id, filename, source_type, chunk_number,
        ROW_NUMBER() OVER (ORDER BY embedding <=> CAST(:embedding AS halfvec)) AS rank
    FROM document_chunks
    WHERE doc_id = ANY(CAST(:allowed_ids AS UUID[]))
    ORDER BY embedding <=> CAST(:embedding AS halfvec)
    LIMIT :limit_val
),
sparse AS (
    SELECT chunk_id, text_chunk, doc_id, filename, source_type, chunk_number,
        ROW_NUMBER() OVER (ORDER BY ts_rank(search_vector, query) DESC) AS rank
    FROM document_chunks, websearch_to_tsquery('english', :query_text) AS query
    WHERE doc_id = ANY(CAST(:allowed_ids AS UUID[]))
      AND websearch_to_tsquery('english', :query_text) IS NOT NULL
      AND search_vector @@ websearch_to_tsquery('english', :query_text)
    ORDER BY ts_rank(search_vector, query) DESC
    LIMIT :limit_val
),
rrf AS (
    SELECT
        COALESCE(d.chunk_id,      s.chunk_id)      AS chunk_id,
        COALESCE(d.text_chunk,    s.text_chunk)     AS text_chunk,
        COALESCE(d.doc_id,        s.doc_id)         AS doc_id,
        COALESCE(d.filename,      s.filename)       AS filename,
        COALESCE(d.source_type,   s.source_type)    AS source_type,
        COALESCE(d.chunk_number,  s.chunk_number)   AS chunk_number,
        -- chunks in both lists get contributions from both legs
        COALESCE(1.0 / (60.0 + d.rank), 0.0) +
        COALESCE(1.0 / (60.0 + s.rank), 0.0) AS rrf_score
    FROM      dense d
    FULL OUTER JOIN sparse s USING (chunk_id)
)
SELECT chunk_id, text_chunk, doc_id, filename, source_type, chunk_number, rrf_score
FROM rrf ORDER BY rrf_score DESC LIMIT :limit_val;
"""


class PgVectorService:
    """
    Retrieval service backed by Supabase/Postgres + pgvector.

    Replaces VectorDBService (ChromaDB). Exposes the same three-method
    interface so no API-layer code needs to change except awaiting the calls.

      - add_documents(documents)   — bulk insert chunks + embeddings
      - query_documents(...)       — hybrid RRF search (dense + sparse)
      - delete_documents(doc_id)   — remove all chunks for a document
    """

    async def ensure_table(self) -> None:
        """
        Idempotently creates the document_chunks table, indexes, and trigger.
        Called once at application startup from main.py lifespan.
        """
        try:
            async with engine.begin() as conn:
                # Execute each command one by one
                for command in _DDL_COMMANDS:
                    await conn.execute(text(command))
            logger.info("document_chunks table and indexes verified/created.")
        except Exception as e:
            logger.error(f"Failed to verify/create document_chunks table: {e}", exc_info=True)
            raise VectorDBError("Database initialization failed", details=str(e))


    async def add_documents(self, documents: List[Dict[str, Any]], db_session: AsyncSession) -> None:
        """
        Bulk-inserts processed chunks into document_chunks using the active SQLAlchemy session.
        This ensures it shares the same transaction as the parent Document creation.
        """
        if not documents:
            logger.info("add_documents called with empty list — nothing to do.")
            return

        # Prepare the raw SQL
        insert_sql = text("""
            INSERT INTO document_chunks
                (chunk_id, doc_id, text_chunk, embedding,
                 chunk_number, filename, source_type)
            VALUES (
                :chunk_id, 
                CAST(:doc_id AS UUID), 
                :text_chunk, 
                CAST(:embedding AS halfvec), 
                :chunk_number, 
                :filename, 
                :source_type
            )
            ON CONFLICT (chunk_id) DO UPDATE SET
                text_chunk    = EXCLUDED.text_chunk,
                embedding     = EXCLUDED.embedding,
                chunk_number  = EXCLUDED.chunk_number,
                filename      = EXCLUDED.filename,
                source_type   = EXCLUDED.source_type
        """)

        # Format the parameters for SQLAlchemy
        params = []
        for doc in documents:
            meta = doc.get("metadata", {})
            embedding_str = "[" + ",".join(str(v) for v in doc["embedding"]) + "]"
            params.append({
                "chunk_id": doc["chunk_id"],
                "doc_id": doc["doc_id"],
                "text_chunk": doc["text_chunk"],
                "embedding": embedding_str,
                "chunk_number": int(meta.get("chunk_number", 0)),
                "filename": str(meta.get("filename", "")),
                "source_type": str(meta.get("source_type", ""))
            })

        try:
            # Execute the raw SQL through the existing SQLAlchemy transaction
            await db_session.execute(insert_sql, params)
            logger.info(f"Successfully staged {len(params)} chunks for insertion (doc_id prefix: {params[0]['doc_id']}).")
        except Exception as e:
            logger.error(f"add_documents failed: {e}", exc_info=True)
            raise VectorDBError(
                message="Failed to insert document chunks into Postgres.",
                details=str(e),
            )

    async def query_documents(
        self,
        query_text: str,
        query_embedding: List[float],
        n_results: int,
        allowed_doc_ids: List[str],
        db_session: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search: dense (pgvector cosine) + sparse (Postgres full-text)
        fused with Reciprocal Rank Fusion (k=60).

        Returns a list of dicts matching the shape the rest of the app expects:
            {
                "chunk_id"  : str,
                "text_chunk": str,
                "metadata"  : {"doc_id", "filename", "source_type", "chunk_number"},
                "rrf_score" : float,   # higher is better
                "distance"  : float,   # kept for backwards-compat; = 1 - rrf_score
            }
        """
        if allowed_doc_ids is not None and len(allowed_doc_ids) == 0:
            logger.warning(
                "query_documents called with empty allowed_doc_ids — "
                "no documents in this session."
            )
            return []

        doc_id_filter = allowed_doc_ids or []

        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        try:
            result = await db_session.execute(
                text(_HYBRID_QUERY),
                {
                    "embedding": embedding_str,
                    "query_text": query_text,
                    "allowed_ids": doc_id_filter,
                    "limit_val": n_results
                }
            )
            
            rows = result.mappings().all()
            
        except Exception as e:
            logger.error(f"query_documents failed: {e}", exc_info=True)
            raise VectorDBError(
                message="Hybrid search query failed.",
                details=str(e),
            )

        results = []
        for row in rows:
            rrf_score = float(row["rrf_score"])
            results.append({
                "chunk_id":   row["chunk_id"],
                "text_chunk": row["text_chunk"],
                "metadata": {
                    "doc_id":       str(row["doc_id"]),
                    "filename":     row["filename"],
                    "source_type":  row["source_type"],
                    "chunk_number": row["chunk_number"],
                },
                "rrf_score": rrf_score,
                # distance kept so any code still referencing it doesn't KeyError;
                # RRF scores are in (0, 1] so 1 - score keeps "lower = worse"
                "distance":  round(1.0 - rrf_score, 6),
            })

        logger.info(
            f"Hybrid search returned {len(results)} chunks "
            f"for query '{query_text[:60]}...' "
            f"across {len(doc_id_filter)} allowed doc(s)."
        )
        return results