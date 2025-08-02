import logging
from fastapi import APIRouter, Depends, HTTPException

from .. import models
from ..core.exceptions import LLMError, QueryProcessingError
from ..dependencies import get_query_processor_serv
from ..services.query_processor import QueryProcessorService

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/query", response_model=models.schemas.InteractionQueryResponse)
async def handle_query(
    request: models.schemas.InteractionQueryRequest,
    qp_service: QueryProcessorService = Depends(get_query_processor_serv),
):
    """
    Handles a user's natural language query using the retrieve-and-synthesize
    RAG pipeline.
    """
    try:
        logger.info(f"Received query: '{request.query_text}'")
        
        # The QueryProcessorService does all the complex orchestration.
        synthesized_answer = await qp_service.process_query(
            query_text=request.query_text, 
            n_results=request.n_results
        )
        
        return models.schemas.QueryResponse(
            original_query=request.query_text,
            synthesized_answer=synthesized_answer
        )
    except (QueryProcessingError, LLMError) as e:
        logger.error(f"Error processing query '{request.query_text}': {e.message}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Error processing your query: {e.message}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while handling query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected server error occurred.")