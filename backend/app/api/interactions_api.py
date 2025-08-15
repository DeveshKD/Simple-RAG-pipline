import logging
import os
import shutil
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import models
from ..database import get_db
from ..core.exceptions import DocumentIngestionError, DocumentProcessingError, VectorDBError, LLMError
from ..dependencies import (
    get_ingestor_factory_serv,
    get_doc_processor_serv,
    get_vector_db_serv,
    get_query_processor_serv
)
from ..services.document_ingestor import DocumentIngestorFactory
from ..services.document_processor import DocumentProcessorService
from ..services.vector_db_service import VectorDBService
from ..services.query_processor import QueryProcessorService
from ..services.auth_service import current_active_user

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIRECTORY = "./temp_uploads"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

@router.post("/interactions/with-document", response_model=models.schemas.DocumentUploadResponse)
async def create_or_update_interaction_with_document(
    interaction_id: Optional[uuid.UUID] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: models.db_models.User = Depends(current_active_user),
    ingestor_factory: DocumentIngestorFactory = Depends(get_ingestor_factory_serv),
    doc_processor: DocumentProcessorService = Depends(get_doc_processor_serv),
    vector_db: VectorDBService = Depends(get_vector_db_serv),
):
    """
    The primary endpoint to add knowledge.
    - If interaction_id is NOT provided, it creates a NEW interaction.
    - If interaction_id IS provided, it adds the document to that existing interaction.
    """
    interaction = None
    if interaction_id is None:
        logger.info(f"User {user.id} creating new interaction with file: {file.filename}")
        interaction = models.db_models.ChatSession(title=file.filename, owner_id=user.id)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)
    else:
        logger.info(f"User {user.id} adding document to interaction '{interaction_id}'")
        statement = select(models.db_models.ChatSession).filter(
            models.db_models.ChatSession.id == interaction_id,
            models.db_models.ChatSession.owner_id == user.id
        )
        result = await db.execute(statement)
        interaction = result.scalar_one_or_none()
        
        if not interaction:
            raise HTTPException(status_code=404, detail="Interaction not found.")

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
        
        # doc-interaction association
        association = models.db_models.interaction_document_association.insert().values(
            interaction_id=interaction.id,
            document_id=new_document_record.id
        )
        await db.execute(association)
        await db.commit()
        
        statement = select(models.db_models.ChatSession).options(
            selectinload(models.db_models.ChatSession.documents)
        ).filter(models.db_models.ChatSession.id == interaction.id)
        result = await db.execute(statement)
        interaction = result.scalar_one()
        
        full_interaction_state = models.schemas.InteractionHistory(
            id=interaction.id,
            title=interaction.title,
            created_at=interaction.created_at.isoformat(),
            documents=[
                models.schemas.DocumentInfo(
                    id=doc.id,
                    filename=doc.filename,
                    source_type=doc.source_type,
                    created_at=doc.created_at.isoformat()
                ) for doc in interaction.documents
            ],
            messages=[
            models.schemas.ChatMessage(
                id=None,
                role="system",
                content=f"Document '{new_document_record.filename}' has been added to this interaction.",
                timestamp=None
            )] if interaction_id is None else []
            )

        return models.schemas.DocumentUploadResponse(
            interaction_state=full_interaction_state
        )

    except (DocumentIngestionError, DocumentProcessingError, VectorDBError, LLMError) as e:
        raise HTTPException(status_code=500, detail=f"A server error occurred: {e.message}")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@router.post("/interactions/{interaction_id}/query", response_model=models.schemas.InteractionQueryResponse)
async def handle_query(
    interaction_id: uuid.UUID,
    request: models.schemas.InteractionQueryRequest,
    db: AsyncSession = Depends(get_db),
    qp_service: QueryProcessorService = Depends(get_query_processor_serv),
    user: models.db_models.User = Depends(current_active_user)
):
    """Handles a user's message within a specific interaction."""
    statement = select(models.db_models.ChatSession).options(
        selectinload(models.db_models.ChatSession.documents),
        selectinload(models.db_models.ChatSession.messages)
    ).filter(
        models.db_models.ChatSession.id == interaction_id,
        models.db_models.ChatSession.owner_id == user.id
    )
    result = await db.execute(statement)
    interaction = result.scalar_one_or_none()
    
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found.")
    
    # First message in a new chat? Add a system message.
    if not interaction.messages:
        system_content = f"Document '{interaction.documents[0].filename}' has been processed. You can now ask questions about its content."
        system_message = models.db_models.ChatMessage(chat_id=interaction_id, role="assistant", content=system_content)
        db.add(system_message)

    user_message = models.db_models.ChatMessage(chat_id=interaction_id, role="user", content=request.query_text)
    db.add(user_message)
    await db.commit()
    await db.refresh(interaction)

    allowed_doc_ids = [str(doc.id) for doc in interaction.documents]
    chat_history_for_prompt = [{"role": msg.role, "content": msg.content} for msg in interaction.messages]
    
    synthesized_answer = await qp_service.process_query(
        query_text=request.query_text,
        n_results=5,
        chat_history=chat_history_for_prompt,
        allowed_doc_ids=allowed_doc_ids
    )
    
    assistant_message = models.db_models.ChatMessage(chat_id=interaction_id, role="assistant", content=synthesized_answer)
    db.add(assistant_message)
    await db.commit()

    return models.schemas.InteractionQueryResponse(
        interaction_id=interaction.id,
        synthesized_answer=synthesized_answer
        )

@router.get("/interactions", response_model=List[models.schemas.InteractionInfo])
async def list_interactions(
    db: AsyncSession = Depends(get_db),
    user: models.db_models.User = Depends(current_active_user)
    ):
    """Lists all past chat sessions, newest first."""
    statement = select(models.db_models.ChatSession).options(
        selectinload(models.db_models.ChatSession.documents)
    ).filter(
        models.db_models.ChatSession.owner_id == user.id
    ).order_by(models.db_models.ChatSession.created_at.desc())
    
    result = await db.execute(statement)
    interactions = result.scalars().all()
    
    response_data = []
    for interaction in interactions:
        response_data.append(
            models.schemas.InteractionInfo(
                id=interaction.id,
                title=interaction.title,
                created_at=interaction.created_at.isoformat() # Convert datetime to string here
            )
        )
    return response_data


@router.get("/interaction/{interaction_id}", response_model=models.schemas.InteractionHistory)
async def get_interaction_history(
    interaction_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    user: models.db_models.User = Depends(current_active_user)
    ):
    """
    Retrieves the full message history AND the list of associated documents
    for a specific chat session.
    """
    statement = select(models.db_models.ChatSession).options(
        selectinload(models.db_models.ChatSession.documents),
        selectinload(models.db_models.ChatSession.messages)
    ).filter(
        models.db_models.ChatSession.id == interaction_id,
        models.db_models.ChatSession.owner_id == user.id
    )
    result = await db.execute(statement)
    interaction = result.scalar_one_or_none()
    
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found.")
    response_data = models.schemas.InteractionHistory(
        id=interaction.id,
        title=interaction.title,
        created_at=interaction.created_at.isoformat(),
        documents=[
            models.schemas.DocumentInfo(
                id=doc.id,
                filename=doc.filename,
                source_type=doc.source_type,
                created_at=doc.created_at.isoformat()
            ) for doc in interaction.documents
        ],
        messages=[
            models.schemas.ChatMessage(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                timestamp=msg.timestamp.isoformat()
            ) for msg in interaction.messages
        ]
    )
    return response_data


@router.delete("/interaction/{interaction_id}", response_model=models.schemas.StatusResponse)
async def delete_interaction(
    interaction_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    user: models.db_models.User = Depends(current_active_user)
    ):
    """Deletes a chat session and all its messages."""
    statement = select(models.db_models.ChatSession).filter(
        models.db_models.ChatSession.id == interaction_id,
        models.db_models.ChatSession.owner_id == user.id
    )
    result = await db.execute(statement)
    interaction = result.scalar_one_or_none()
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found.")
    
    await db.delete(interaction)
    await db.commit()
    logger.info(f"Deleted interaction with ID: {interaction_id}")
    return models.schemas.StatusResponse(status="success", message=f"Interaction {interaction_id} deleted.")

@router.delete("/interaction/{interaction_id}/unlink-document/{document_id}", response_model=models.schemas.StatusResponse)
async def unlink_document_from_interaction(
    interaction_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: models.db_models.User = Depends(current_active_user)
):
    """
    Removes the association between a document and a chat interaction.
    Both the document and interaction data remain intact - only the link is removed.
    This should be added to interactions_api.py
    """
    logger.info(f"User {user.id} unlinking document {document_id} from interaction {interaction_id}")

    # Verify interaction ownership
    interaction_statement = select(models.db_models.ChatSession).filter(
        models.db_models.ChatSession.id == interaction_id,
        models.db_models.ChatSession.owner_id == user.id
    )
    interaction_result = await db.execute(interaction_statement)
    interaction = interaction_result.scalar_one_or_none()

    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found.")

    # Verify document ownership and that it's linked to this interaction
    doc_statement = select(models.db_models.Document).filter(
        models.db_models.Document.id == document_id,
        models.db_models.Document.owner_id == user.id
    )
    doc_result = await db.execute(doc_statement)
    document = doc_result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Check if the association exists
    existing_association = await db.execute(
        select(models.db_models.interaction_document_association).where(
            models.db_models.interaction_document_association.c.interaction_id == interaction_id,
            models.db_models.interaction_document_association.c.document_id == document_id
        )
    )
    if not existing_association.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Document is not linked to this interaction.")

    try:
        # Delete association
        delete_statement = delete(models.db_models.interaction_document_association).where(
            models.db_models.interaction_document_association.c.interaction_id == interaction_id,
            models.db_models.interaction_document_association.c.document_id == document_id
        )
        await db.execute(delete_statement)
        await db.commit()

        return models.schemas.StatusResponse(
            status="success",
            message=f"Document '{document.filename}' unlinked from interaction '{interaction.title}' successfully."
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected server error occurred while unlinking document.")