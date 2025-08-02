import logging
import os
import shutil
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..core.exceptions import DocumentIngestionError, DocumentProcessingError, VectorDBError, LLMError
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

UPLOAD_DIRECTORY = "./temp_uploads"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

@router.post("/documents/upload/{interaction_id}", response_model=models.schemas.DocumentUploadResponse)
async def upload_document_to_interaction(
    interaction_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    ingestor_factory: DocumentIngestorFactory = Depends(get_ingestor_factory_serv),
    doc_processor: DocumentProcessorService = Depends(get_doc_processor_serv),
    vector_db: VectorDBService = Depends(get_vector_db_serv),
):
    """
    Uploads a document and associates it with a specific interaction session.
    """
    interaction = db.query(models.db_models.ChatSession).filter(models.db_models.ChatSession.id == interaction_id).first()
    if not interaction:
        raise HTTPException(status_code=404, detail=f"Interaction with ID {interaction_id} not found.")

    temp_file_path = os.path.join(UPLOAD_DIRECTORY, file.filename)
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        ingestor = ingestor_factory.create_ingestor(temp_file_path)
        raw_doc = ingestor.ingest_document() 
        
        new_document_record = models.db_models.Document(
            filename=file.filename,
            source_type=raw_doc["metadata"].get("source_type")
        )
        db.add(new_document_record)
        db.commit()
        db.refresh(new_document_record)
        
        doc_id_for_chroma = str(new_document_record.id)
        raw_doc["doc_id"] = doc_id_for_chroma 

        processed_chunks = await doc_processor.process_documents([raw_doc])
        if not processed_chunks:
            raise HTTPException(status_code=422, detail="Failed to process document. No chunks were generated.")
        

        vector_db.add_documents(processed_chunks)

        interaction.documents.append(new_document_record)
        db.commit()

        logger.info(f"Successfully processed and linked document '{file.filename}' to interaction '{interaction_id}'.")
        
        return models.schemas.DocumentUploadResponse(
            message="File processed and linked to the interaction.",
            filename=file.filename,
            doc_id=doc_id_for_chroma,
            chunks_added=len(processed_chunks)
        )
    except (DocumentIngestionError, DocumentProcessingError, VectorDBError, LLMError) as e:
        raise HTTPException(status_code=500, detail=f"A server error occurred: {e.message}")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@router.get("/documents", response_model=List[models.schemas.DocumentInfo])
async def list_all_documents(db: Session = Depends(get_db)):
    """
    Retrieves a list of all unique documents in the system's library.
    This is not session-specific.
    """
    documents_from_db = db.query(models.db_models.Document).order_by(models.db_models.Document.created_at.desc()).all()
    response_data = []
    for doc in documents_from_db:
        response_data.append(
            models.schemas.DocumentInfo(
                id=str(doc.id),
                filename=doc.filename,
                source_type=doc.source_type,
                created_at=doc.created_at.isoformat()
            )
        )
    return response_data
    
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