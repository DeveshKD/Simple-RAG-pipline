import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from .. import models
from ..database import get_db
from ..core.exceptions import LLMError, QueryProcessingError
from ..dependencies import get_query_processor_serv
from ..services.query_processor import QueryProcessorService

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/interaction", response_model=models.schemas.InteractionResponse)
async def handle_interaction(
    request: models.schemas.InteractionRequest,
    db: Session = Depends(get_db),
    qp_service: QueryProcessorService = Depends(get_query_processor_serv)
):
    """
    The unified endpoint for handling a conversation turn.
    - If interaction_id is null, a new chat session is created.
    - If interaction_id is provided, it continues the existing chat.
    """
    try:
        interaction_id = request.interaction_id
        
        if interaction_id is None:
            logger.info("No interaction_id provided. Creating a new chat session.")
            new_interaction = models.db_models.ChatSession(title=request.query_text[:75])
            db.add(new_interaction)
            db.commit()
            db.refresh(new_interaction)
            interaction_id = new_interaction.id
        else:
            logger.info(f"Query for an existing chat: {interaction_id}")
            interaction = db.query(models.db_models.ChatSession).filter(models.db_models.ChatSession.id == interaction_id).first()
            if not interaction:
                raise HTTPException(status_code=404, detail=f"Interaction with ID {interaction_id} not found.")
        
        user_message = models.db_models.ChatMessage(
            chat_id=interaction_id,
            role="user",
            content=request.query_text
        )
        db.add(user_message)
        db.commit()

        # refactor query processor to actually use chat history
        chat_history = [] # adding it here so that i dont forget
        synthesized_answer = await qp_service.process_query(
            query_text=request.query_text,
            n_results=5,
            # chat_history=chat_history (to be added)
        )
        
        assistant_message = models.db_models.ChatMessage(
            chat_id=interaction_id,
            role="assistant",
            content=synthesized_answer
        )
        db.add(assistant_message)
        db.commit()

        return models.schemas.InteractionResponse(
            interaction_id=interaction_id,
            synthesized_answer=synthesized_answer
        )
    except (QueryProcessingError, LLMError) as e:
        raise HTTPException(status_code=503, detail=e.message)
    except Exception as e:
        logger.error(f"An unexpected error occurred in handle_interaction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected server error occurred.")


@router.get("/interactions", response_model=List[models.schemas.InteractionInfo])
async def list_interactions(db: Session = Depends(get_db)):
    """Lists all past chat sessions, newest first."""
    interactions = db.query(models.db_models.ChatSession).order_by(models.db_models.ChatSession.created_at.desc()).all()
    return interactions


@router.get("/interaction/{interaction_id}", response_model=models.schemas.InteractionHistory)
async def get_interaction_history(interaction_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieves the full message history for a specific chat session."""
    interaction = db.query(models.db_models.ChatSession).filter(models.db_models.ChatSession.id == interaction_id).first()
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found.")
    return interaction


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