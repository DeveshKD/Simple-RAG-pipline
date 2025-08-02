from pydantic import BaseModel, EmailStr, Field, field_serializer
from typing import List, Dict, Any, Optional
import uuid

#v1 schemas (some still required and some not)
class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class DocumentMetadata(BaseModel):
    """
    A flexible container for metadata associated with a document chunk.
    This structure is used internally and can be part of API responses.
    """
    source_file: Optional[str] = None
    source_type: Optional[str] = Field(None, description="The type of the source file, e.g., 'pdf', 'csv', 'txt'")
    page_count: Optional[int] = None
    row_count: Optional[int] = None
    column_headers: Optional[List[str]] = None
    chunk_number: Optional[int] = None

class DocumentInfo(BaseModel):
    """A summary of a single document."""
    id: uuid.UUID
    filename: str
    source_type: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True

    @field_serializer('created_at')
    def serialize_dt(self, dt: Any, _info):
        if isinstance(dt, str): return dt
        return dt.isoformat()

class DocumentUploadResponse(BaseModel):
    """Response after a document is uploaded to an interaction."""
    interaction_id: uuid.UUID
    document: DocumentInfo

class ListDocumentsResponse(BaseModel):
    """
    The response containing a list of all documents currently in the vector store.
    """
    total_documents: int = Field(..., description="The total number of unique documents in the system.")
    documents: List[DocumentInfo] = Field(..., description="A list containing summary information for each document.")


class StatusResponse(BaseModel):
    """
    A generic response model for endpoints that return a simple status message,
    often used for administrative tasks.
    """
    status: str
    message: Optional[str] = None

# schemas for v2
class InteractionQueryRequest(BaseModel):
    """
    The request model for the unified interaction endpoint.
    """
    query_text: str = Field(..., min_length=1, description="the user query")

class InteractionQueryResponse(BaseModel):
    """
    The response from the unified interaction endpoint, containing the AI's
    answer and the ID of the interaction session.
    """
    interaction_id: uuid.UUID = Field(..., description="The ID of the chat session.")
    synthesized_answer: str = Field(..., description="AI's response to the user's query.")

class ChatMessage(BaseModel):
    """
    Represents a single message within a chat history.
    """
    id : uuid.UUID
    role: str
    content: str
    timestamp: Optional[str] = None

    class Config:
        from_attributes = True 

class InteractionInfo(BaseModel):
    """
    A summary of a single interaction, used for listing all past chats.
    """
    id: uuid.UUID
    title: str
    created_at: str
    documents: List[DocumentInfo] = []
    class Config:
        from_attributes = True

class InteractionHistory(InteractionInfo):
    """

    Represents the full details of a single interaction, including all messages.
    """
    messages: List[ChatMessage] = []

    class Config:
        from_attributes = True