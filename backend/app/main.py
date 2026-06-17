import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.exceptions import VectorDBError
from .api import documents_api, interactions_api, auth_api, library_api
from . import dependencies as deps
from .database import engine

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ------------------------------------------------------------------ startup
    logger.info("Application startup...")
    try:
        deps.document_ingestor_factory = deps.DocumentIngestorFactory()
        deps.document_processor_service = deps.DocumentProcessorService()

        # PgVectorService replaces VectorDBService (ChromaDB).
        # ensure_table() is idempotent — safe to run on every boot.
        from .services.pgvector_service import PgVectorService
        pgvector = PgVectorService()
        await pgvector.ensure_table()
        deps.vector_db_service = pgvector

        deps.query_processor_service = deps.QueryProcessorService(
            vector_db_service=deps.vector_db_service
        )

        logger.info("All application services initialized successfully.")

    except VectorDBError as e:
        logger.critical(
            f"CRITICAL: Failed to initialize PgVectorService. "
            f"Application cannot start. Error: {e.message}",
            exc_info=True,
        )
    except Exception as e:
        logger.critical(
            f"CRITICAL: Unexpected error during service initialization: {e}",
            exc_info=True,
        )

    yield

    # ----------------------------------------------------------------- shutdown
    logger.info("Application shutdown...")
    await engine.dispose()                      # closes SQLAlchemy engine


app = FastAPI(
    title=settings.project_name,
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

origins = [
    "http://localhost",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_api.router,         prefix="/api/v2", tags=["Authentication"])
app.include_router(interactions_api.router, prefix="/api/v2", tags=["V2 - Interactions (Stateful)"])
app.include_router(library_api.router,      prefix="/api",    tags=["library"])


@app.get("/", tags=["Root"])
async def read_root():
    return {"message": f"Welcome to the {settings.project_name} API!"}