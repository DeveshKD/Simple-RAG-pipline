import logging
import os
import shutil
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from ..services.auth_service import current_active_user

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIRECTORY = "./temp_uploads"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

@router.get("/library/documents", response_model=List[models.schemas.DocumentLibraryInfo])
async def list_user_library_documents(
    db: AsyncSession = Depends(get_db),
    user: models.db_models.User = Depends(current_active_user)
):
    """
    Lists all documents owned by the user with their associated chat sessions.
    This gives a complete view of the user's document library.
    """
    logger.info(f"Fetching library documents for user: {user.id}")
    
    statement = select(models.db_models.Document).options(
        selectinload(models.db_models.Document.interactions)
    ).filter(
        models.db_models.Document.owner_id == user.id
    ).order_by(models.db_models.Document.created_at.desc())
    
    result = await db.execute(statement)
    documents_from_db = result.scalars().all()
    
    response_data = []
    for doc in documents_from_db:
        # Get associated interactions info
        linked_sessions = []
        for interaction in doc.interactions:
            linked_sessions.append(
                models.schemas.InteractionInfo(
                    id=interaction.id,
                    title=interaction.title,
                    created_at=interaction.created_at.isoformat()
                )
            )
        
        response_data.append(
            models.schemas.DocumentLibraryInfo(
                id=str(doc.id),
                filename=doc.filename,
                source_type=doc.source_type,
                created_at=doc.created_at.isoformat(),
                linked_sessions=linked_sessions
            )
        )
    return response_data


@router.delete("/library/document/{document_id}", response_model=models.schemas.StatusResponse)
async def delete_library_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    vector_db: VectorDBService = Depends(get_vector_db_serv),
    user: models.db_models.User = Depends(current_active_user)
):
    """
    Completely deletes a document from the library:
    1. Removes all document-interaction associations
    2. Deletes document from vector store
    3. Deletes document record from database
    Chat sessions and their messages remain untouched.
    """
    logger.warning(f"User {user.id} attempting to delete library document {document_id}")

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
        
        # Finally delete the document record
        await db.delete(document_to_delete)
        await db.commit()

        return models.schemas.StatusResponse(
            status="success",
            message=f"Document '{document_to_delete.filename}' has been permanently deleted from library."
        )
    except VectorDBError as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document from vector store: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected server error occurred during document deletion.")


@router.post("/library/document/upload", response_model=models.schemas.DocumentUploadToLibraryResponse)
async def upload_document_to_library(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: models.db_models.User = Depends(current_active_user),
    ingestor_factory: DocumentIngestorFactory = Depends(get_ingestor_factory_serv),
    doc_processor: DocumentProcessorService = Depends(get_doc_processor_serv),
    vector_db: VectorDBService = Depends(get_vector_db_serv),
):
    """
    Uploads a document to the user's library without associating it with any chat session.
    The document can later be linked to specific interactions.
    """
    logger.info(f"User {user.id} uploading document to library: {file.filename}")

    temp_file_path = os.path.join(UPLOAD_DIRECTORY, file.filename)
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        raw_doc = ingestor_factory.create_ingestor(temp_file_path).ingest_document()
        
        new_document_record = models.db_models.Document(
            filename=file.filename,
            source_type=raw_doc["metadata"].get("source_type"),
            owner_id=user.id
        )
        db.add(new_document_record)
        await db.commit()
        await db.refresh(new_document_record)
        
        doc_id_for_chroma = str(new_document_record.id)
        raw_doc["doc_id"] = doc_id_for_chroma

        processed_chunks = await doc_processor.process_documents([raw_doc])
        if not processed_chunks:
            raise HTTPException(status_code=422, detail="Failed to process document. No chunks were generated.")
        
        vector_db.add_documents(processed_chunks)
        
        return models.schemas.DocumentUploadToLibraryResponse(
            document=models.schemas.DocumentInfo(
                id=new_document_record.id,
                filename=new_document_record.filename,
                source_type=new_document_record.source_type,
                created_at=new_document_record.created_at.isoformat()
            ),
            message=f"Document '{file.filename}' uploaded to library successfully."
        )

    except (DocumentIngestionError, DocumentProcessingError, VectorDBError, LLMError) as e:
        raise HTTPException(status_code=500, detail=f"A server error occurred: {e.message}")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@router.post("/library/document/{document_id}/link-to/{interaction_id}", response_model=models.schemas.StatusResponse)
async def link_document_to_interaction(
    document_id: uuid.UUID,
    interaction_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: models.db_models.User = Depends(current_active_user)
):
    """
    Links an existing library document to an existing chat interaction.
    Both the document and interaction must be owned by the current user.
    """
    logger.info(f"User {user.id} linking document {document_id} to interaction {interaction_id}")

    # Verify document ownership
    doc_statement = select(models.db_models.Document).filter(
        models.db_models.Document.id == document_id,
        models.db_models.Document.owner_id == user.id
    )
    doc_result = await db.execute(doc_statement)
    document = doc_result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Verify interaction ownership
    interaction_statement = select(models.db_models.ChatSession).filter(
        models.db_models.ChatSession.id == interaction_id,
        models.db_models.ChatSession.owner_id == user.id
    )
    interaction_result = await db.execute(interaction_statement)
    interaction = interaction_result.scalar_one_or_none()

    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found.")

    # Check if already linked
    existing_association = await db.execute(
        select(models.db_models.interaction_document_association).where(
            models.db_models.interaction_document_association.c.interaction_id == interaction_id,
            models.db_models.interaction_document_association.c.document_id == document_id
        )
    )
    if existing_association.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Document is already linked to this interaction.")

    try:
        # Create the association
        association = models.db_models.interaction_document_association.insert().values(
            interaction_id=interaction_id,
            document_id=document_id
        )
        await db.execute(association)
        await db.commit()

        return models.schemas.StatusResponse(
            status="success",
            message=f"Document '{document.filename}' linked to interaction '{interaction.title}' successfully."
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected server error occurred while linking document.")


@router.get("/library/document/{document_id}/available-interactions", response_model=List[models.schemas.InteractionInfo])
async def get_available_interactions_for_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: models.db_models.User = Depends(current_active_user)
):
    """
    Lists all chat interactions that are NOT currently linked to the specified document.
    This helps users see which interactions they can link the document to.
    """
    logger.info(f"User {user.id} fetching available interactions for document {document_id}")

    # Verify document ownership
    doc_statement = select(models.db_models.Document).filter(
        models.db_models.Document.id == document_id,
        models.db_models.Document.owner_id == user.id
    )
    doc_result = await db.execute(doc_statement)
    document = doc_result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Get all interactions for this user that are NOT linked to this document
    linked_interaction_ids = select(
        models.db_models.interaction_document_association.c.interaction_id
    ).where(
        models.db_models.interaction_document_association.c.document_id == document_id
    )

    available_interactions_statement = select(models.db_models.ChatSession).filter(
        models.db_models.ChatSession.owner_id == user.id,
        ~models.db_models.ChatSession.id.in_(linked_interaction_ids)
    ).order_by(models.db_models.ChatSession.created_at.desc())

    result = await db.execute(available_interactions_statement)
    available_interactions = result.scalars().all()

    response_data = []
    for interaction in available_interactions:
        response_data.append(
            models.schemas.InteractionInfo(
                id=interaction.id,
                title=interaction.title,
                created_at=interaction.created_at.isoformat()
            )
        )

    return response_data