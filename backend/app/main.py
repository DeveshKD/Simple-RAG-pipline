import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .core.config import settings
from .core.exceptions import VectorDBError
from .api import documents_api, query_api, interactions_api
from . import dependencies as deps
from .database import engine
from .models import db_models

# Configure Logging
logging.basicConfig(
    level=settings.log_level.upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Lifespan Manager for Service Initialization
# This async context manager handles what happens on application startup and shutdown.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("Application startup...")
    
    # Initialize all services and store them in the shared 'deps' module.
    # This ensures we have a single, shared instance of each service.
    try:
        deps.document_ingestor_factory = deps.DocumentIngestorFactory()
        deps.document_processor_service = deps.DocumentProcessorService()
        deps.vector_db_service = deps.VectorDBService()
        
        # The QueryProcessorService depends on the VectorDBService.
        deps.query_processor_service = deps.QueryProcessorService(
            vector_db_service=deps.vector_db_service
        )
        logger.info("Initializing database and creating tables if they don't exist...")
        db_models.Base.metadata.create_all(bind=engine)
        logger.info("All application services initialized successfully.")
    
    except VectorDBError as e:
        # If the vector DB fails to initialize, the app is not usable.
        logger.critical(f"CRITICAL: Failed to initialize VectorDB. Application cannot start. Error: {e.message}", exc_info=True)
        # For now, we log a critical error. The dependency functions will raise RuntimErrors.
        
    except Exception as e:
        logger.critical(f"CRITICAL: An unexpected error occurred during service initialization: {e}", exc_info=True)
        
    yield
    # --- Shutdown ---
    logger.info("Application shutdown...")
    # any cleanup tasks here if needed (e.g., closing database connections).
    # ChromaDB's persistent client handles its own shutdown gracefully.


# Create FastAPI Application Instance
# Use the lifespan manager to handle startup/shutdown events.
app = FastAPI(
    title=settings.project_name,
    openapi_url=f"/api/v1/openapi.json", # Standard location for OpenAPI spec
    lifespan=lifespan
)

# Include API Routers
app.include_router(documents_api.router, prefix="/api/v1", tags=["Documents"])
app.include_router(query_api.router, prefix="/api/v1", tags=["V1 Query"])
app.include_router(interactions_api.router, prefix="/api/v2", tags=["V2 - Interactions (Stateful)"])

# Root Endpoint
@app.get("/", tags=["Root"])
async def read_root():
    """
    A simple health check endpoint to confirm the API is running.
    """
    return {"message": f"Welcome to the {settings.project_name} API!"}