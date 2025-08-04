import logging
import os
import shutil
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session

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

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIRECTORY = "./temp_uploads"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

@router.post("/interactions/with-document", response_model=models.schemas.DocumentUploadResponse)
async def create_or_update_interaction_with_document(
    interaction_id: Optional[uuid.UUID] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
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
        logger.info(f"No interaction_id provided. Creating a new interaction based on file: {file.filename}")
        interaction = models.db_models.ChatSession(title=file.filename)
        db.add(interaction)
        db.commit()
        db.refresh(interaction)
    else:
        logger.info(f"Adding document '{file.filename}' to existing interaction '{interaction_id}'")
        interaction = db.query(models.db_models.ChatSession).filter(models.db_models.ChatSession.id == interaction_id).first()
        if not interaction:
            raise HTTPException(status_code=404, detail="Interaction not found.")

    temp_file_path = os.path.join(UPLOAD_DIRECTORY, file.filename)
    try:
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        raw_doc = ingestor_factory.create_ingestor(temp_file_path).ingest_document()
        
        new_document_record = models.db_models.Document(filename=file.filename, source_type=raw_doc["metadata"].get("source_type"))
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
        db.refresh(interaction)
        
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
                    id=msg.id,
                    role=msg.role,
                    content=msg.content,
                    timestamp=msg.timestamp.isoformat()
                ) for msg in interaction.messages
            ]
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
    db: Session = Depends(get_db),
    qp_service: QueryProcessorService = Depends(get_query_processor_serv)
):
    """Handles a user's message within a specific interaction."""
    interaction = db.query(models.db_models.ChatSession).filter(models.db_models.ChatSession.id == interaction_id).first()
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found.")
    
    # First message in a new chat? Add a system message.
    if not interaction.messages:
        system_content = f"Document '{interaction.documents[0].filename}' has been processed. You can now ask questions about its content."
        system_message = models.db_models.ChatMessage(chat_id=interaction_id, role="assistant", content=system_content)
        db.add(system_message)

    user_message = models.db_models.ChatMessage(chat_id=interaction_id, role="user", content=request.query_text)
    db.add(user_message)
    db.commit()
    db.refresh(interaction)

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
    db.commit()

    return models.schemas.InteractionQueryResponse(
        interaction_id=interaction.id,
        synthesized_answer=synthesized_answer
        )

@router.get("/interactions", response_model=List[models.schemas.InteractionInfo])
async def list_interactions(db: Session = Depends(get_db)):
    """Lists all past chat sessions, newest first."""
    interactions = db.query(models.db_models.ChatSession).order_by(models.db_models.ChatSession.created_at.desc()).all()
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
async def get_interaction_history(interaction_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retrieves the full message history AND the list of associated documents
    for a specific chat session.
    """
    interaction = db.query(models.db_models.ChatSession).filter(models.db_models.ChatSession.id == interaction_id).first()
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
async def delete_interaction(interaction_id: uuid.UUID, db: Session = Depends(get_db)):
    """Deletes a chat session and all its messages."""
    interaction = db.query(models.db_models.ChatSession).filter(models.db_models.ChatSession.id == interaction_id).first()
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found.")
    
    db.delete(interaction)
    db.commit()
    logger.info(f"Deleted interaction with ID: {interaction_id}")
    return models.schemas.StatusResponse(status="success", message=f"Interaction {interaction_id} deleted.")