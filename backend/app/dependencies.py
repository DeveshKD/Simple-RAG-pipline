import logging
from .services.document_ingestor import DocumentIngestorFactory
from .services.document_processor import DocumentProcessorService
from .services.pgvector_service import PgVectorService
from .services.query_processor import QueryProcessorService

logger = logging.getLogger(__name__)

# --- Service Instances ---
# All set to None here; main.py lifespan manager creates the real instances.
document_ingestor_factory: DocumentIngestorFactory | None = None
document_processor_service: DocumentProcessorService | None = None
vector_db_service: PgVectorService | None = None
query_processor_service: QueryProcessorService | None = None

# --- Dependency provider functions for FastAPI Depends() ---

def get_ingestor_factory_serv() -> DocumentIngestorFactory:
    if document_ingestor_factory is None:
        raise RuntimeError("DocumentIngestorFactory not initialized.")
    return document_ingestor_factory

def get_doc_processor_serv() -> DocumentProcessorService:
    if document_processor_service is None:
        raise RuntimeError("DocumentProcessorService not initialized.")
    return document_processor_service

def get_vector_db_serv() -> PgVectorService:
    if vector_db_service is None:
        raise RuntimeError("PgVectorService not initialized.")
    return vector_db_service

def get_query_processor_serv() -> QueryProcessorService:
    if query_processor_service is None:
        raise RuntimeError("QueryProcessorService not initialized.")
    return query_processor_service

logger.info("Service dependency providers defined.")