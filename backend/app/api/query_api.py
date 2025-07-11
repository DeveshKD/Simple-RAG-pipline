from fastapi import APIRouter, Depends, Query
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/v1", tags=["RAG"])

@router.get("/ask")
def ask_question(
    question: str = Query(..., description="The user’s question about uploaded docs"),
    user: dict = Depends(get_current_user),
):
    """
    Protected endpoint: user is guaranteed to be a valid, authenticated user dict.
    """
    # Pass both the question and the user context into your service
    answer = "This is a mock answer to the question: " + question
    return {
        "username": user["username"],
        "question": question,
        "answer": answer,
    }