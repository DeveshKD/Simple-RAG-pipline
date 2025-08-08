import logging
from .services.document_ingestor import DocumentIngestorFactory
from .services.document_processor import DocumentProcessorService
from .services.vector_db_service import VectorDBService
from .services.query_processor import QueryProcessorService

# This file creates "singleton" instances of the services that the whole
# application will share. This is efficient and manages state correctly.

logger = logging.getLogger(__name__)

# --- Service Instances (will be initialized by main.py on startup) ---
# We define them here as None, and the main app's lifespan manager will create them.
document_ingestor_factory: DocumentIngestorFactory | None = None
document_processor_service: DocumentProcessorService | None = None
vector_db_service: VectorDBService | None = None
query_processor_service: QueryProcessorService | None = None

# --- Dependency Provider Functions for FastAPI ---
# These functions are what FastAPI's `Depends()` will call.

def get_ingestor_factory_serv() -> DocumentIngestorFactory:
    if document_ingestor_factory is None:
        raise RuntimeError("DocumentIngestorFactory not initialized.")
    return document_ingestor_factory

def get_doc_processor_serv() -> DocumentProcessorService:
    if document_processor_service is None:
        raise RuntimeError("DocumentProcessorService not initialized.")
    return document_processor_service

def get_vector_db_serv() -> VectorDBService:
    if vector_db_service is None:
        raise RuntimeError("VectorDBService not initialized.")
    return vector_db_service

def get_query_processor_serv() -> QueryProcessorService:
    if query_processor_service is None:
        raise RuntimeError("QueryProcessorService not initialized.")
    return query_processor_service

logger.info("Service dependency providers defined.")