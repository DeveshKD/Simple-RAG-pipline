import logging
import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile

from .. import models
from ..core.exceptions import DocumentIngestionError, DocumentProcessingError, VectorDBError
from ..dependencies import (
    get_ingestor_factory_serv,
    get_doc_processor_serv,
    get_vector_db_serv,
)
from ..services.document_ingestor import DocumentIngestorFactory
from ..services.document_processor import DocumentProcessorService
from ..services.vector_db_service import VectorDBService

logger = logging.getLogger(__name__)
router = APIRouter()

# Define a directory to temporarily store uploads. In a real production
# system, this would be a more robust solution like S3.
UPLOAD_DIRECTORY = "./backend/data/uploads"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

@router.post("/documents/upload", response_model=models.schemas.DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    ingestor_factory: DocumentIngestorFactory = Depends(get_ingestor_factory_serv),
    doc_processor: DocumentProcessorService = Depends(get_doc_processor_serv),
    vector_db: VectorDBService = Depends(get_vector_db_serv),
):
    """
    Handles the end-to-end processing of a single uploaded file.
    1. Saves the file temporarily.
    2. Ingests raw text and metadata using the appropriate ingestor.
    3. Processes the raw data (cleans, chunks, embeds).
    4. Adds the final processed chunks to the vector database.
    """
    temp_file_path = os.path.join(UPLOAD_DIRECTORY, file.filename)

    try:
        # Save the uploaded file to a temporary path
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"File '{file.filename}' temporarily saved to '{temp_file_path}'.")

        # --- The RAG Ingestion Pipeline ---
        # 1. Ingest
        ingestor = ingestor_factory.create_ingestor(temp_file_path)
        raw_doc = ingestor.ingest_document()

        # 2. Process
        # The processor expects a list of documents
        processed_chunks = await doc_processor.process_documents([raw_doc])

        # 3. Store
        if processed_chunks:
            vector_db.add_documents(processed_chunks)
        else:
            logger.warning(f"No processable chunks were generated for file '{file.filename}'.")
            
        return models.schemas.DocumentUploadResponse(
            message="File processed successfully.",
            filename=file.filename,
            doc_id=raw_doc["doc_id"],
            chunks_added=len(processed_chunks)
        )
    except ValueError as e: # Catches unsupported file types from the factory
        logger.error(f"Unsupported file type for '{file.filename}': {e}")
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {str(e)}")
    except (DocumentIngestionError, DocumentProcessingError, VectorDBError) as e:
        logger.error(f"Error processing file '{file.filename}': {e.message}", exc_info=True)
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        logger.error(f"An unexpected error occurred during file upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected server error occurred.")
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        logger.info(f"Temporary file '{temp_file_path}' removed.")


@router.get("/documents", response_model=models.schemas.ListDocumentsResponse)
async def list_documents(vector_db: VectorDBService = Depends(get_vector_db_serv)):
    """
    Retrieves a list of all unique documents that have been ingested.
    It does this by querying all chunks and de-duplicating by doc_id.
    """
    try:
        all_chunks = vector_db.get_all_documents()
        
        unique_docs = {}
        for chunk in all_chunks:
            metadata = chunk.get("metadata", {})
            doc_id = metadata.get("doc_id")
            if doc_id and doc_id not in unique_docs:
                unique_docs[doc_id] = models.schemas.DocumentInfo(
                    doc_id=doc_id,
                    filename=metadata.get("filename"),
                    source_type=metadata.get("source_type")
                )
        
        doc_list = list(unique_docs.values())
        return models.schemas.ListDocumentsResponse(
            total_documents=len(doc_list),
            documents=doc_list
        )
    except VectorDBError as e:
        logger.error(f"Failed to list documents from VectorDB: {e.message}", exc_info=True)
        raise HTTPException(status_code=500, detail=e.message)
    
@router.delete("/documents/clear-all", response_model=models.schemas.StatusResponse)
async def clear_all_documents(vector_db: VectorDBService = Depends(get_vector_db_serv)):
    """
    Deletes all documents from the vector database. This is an administrative
    action to reset the knowledge base.
    """
    logger.warning("Received request to clear all documents from the knowledge base.")
    try:
        vector_db.clear_collection()
        return models.schemas.StatusResponse(
            status="success",
            message="Knowledge base has been cleared successfully."
        )
    except VectorDBError as e:
        logger.error(f"Failed to clear knowledge base: {e.message}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear knowledge base: {e.message}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while clearing the knowledge base: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected server error occurred.")