import uuid
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Uuid, primary_key=True, default = uuid.uuid4)
    title = Column(String, default="New Chat")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # This creates the relationship to access chat.messages
    messages = relationship("ChatMessage", back_populates="chat_session", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Uuid, primary_key=True, default = uuid.uuid4)
    chat_id = Column(Uuid, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # This creates the relationship back to the parent ChatSession
    chat_session = relationship("ChatSession", back_populates="messages")