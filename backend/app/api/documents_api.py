import logging
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .. import models
from ..database import get_db
from ..core.exceptions import VectorDBError
from ..dependencies import get_vector_db_serv
from ..services.vector_db_service import VectorDBService
from ..services.auth_service import current_active_user

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/documents", response_model=List[models.schemas.DocumentInfo])
async def list_user_documents(
    db: AsyncSession = Depends(get_db),
    user: models.db_models.User = Depends(current_active_user)
):
    """
    Retrieves a list of all documents owned by the currently authenticated user.
    """
    logger.info(f"Fetching all documents for user: {user.id}")
    statement = select(models.db_models.Document).filter(
        models.db_models.Document.owner_id == user.id
    ).order_by(models.db_models.Document.created_at.desc())
    
    result = await db.execute(statement)
    documents_from_db = result.scalars().all()
    
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
    db: AsyncSession = Depends(get_db),
    vector_db: VectorDBService = Depends(get_vector_db_serv),
    user: models.db_models.User = Depends(current_active_user)
):
    logger.warning(f"User {user.id} attempting to delete document {document_id}")

    statement = select(models.db_models.Document).filter(
        models.db_models.Document.id == document_id,
        models.db_models.Document.owner_id == user.id
    )
    result = await db.execute(statement)
    document_to_delete = result.scalar_one_or_none()

    if not document_to_delete:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        vector_db.delete_documents(doc_id=str(document_id))
        await db.delete(document_to_delete)
        await db.commit()

        return models.schemas.StatusResponse(
            status="success",
            message=f"Document '{document_to_delete.filename}' has been deleted."
        )
    except VectorDBError as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document from vector store: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected server error occurred during document deletion.")