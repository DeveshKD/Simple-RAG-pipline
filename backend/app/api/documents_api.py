import logging
import os
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..core.exceptions import VectorDBError
from ..dependencies import (
    get_vector_db_serv,
)
from ..services.vector_db_service import VectorDBService

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIRECTORY = "./temp_uploads"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

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
    
@router.delete("/document/{document_id}", response_model=models.schemas.StatusResponse)
async def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    vector_db: VectorDBService = Depends(get_vector_db_serv)
):
    """
    Deletes a document completely from the system:
    1. Deletes all its chunks from the vector store (ChromaDB).
    2. Deletes its metadata record from the primary database (SQL).
    """
    logger.warning(f"Received request to delete document with ID: {document_id}")

    # Find the document in our primary SQL database first
    document_to_delete = db.query(models.db_models.Document).filter(models.db_models.Document.id == document_id).first()
    if not document_to_delete:
        raise HTTPException(status_code=404, detail="Document not found in the primary database.")

    try:
        # Step 1: Delete from the vector store
        # We must convert the UUID to a string for the metadata filter
        vector_db.delete_documents(doc_id=str(document_id))

        # Step 2: If the vector store deletion was successful, delete from SQL
        db.delete(document_to_delete)
        db.commit()

        return models.schemas.StatusResponse(
            status="success",
            message=f"Document '{document_to_delete.filename}' and all its associated data have been deleted."
        )
    except VectorDBError as e:
        logger.error(f"Failed to delete document from vector store: {e.message}", exc_info=True)
        # 500 because it's a server-side data consistency issue
        raise HTTPException(status_code=500, detail=f"Failed to delete document from vector store: {e.message}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during document deletion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected server error occurred.")