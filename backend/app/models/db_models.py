import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Table, Uuid, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

interaction_document_association = Table(
    'interaction_document_association',
    Base.metadata,
    Column('interaction_id', Uuid, ForeignKey('chat_sessions.id'), primary_key=True),
    Column('document_id', Uuid, ForeignKey('documents.id'), primary_key=True)
)

class User(Base):
    __tablename__ = "users"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    chat_sessions = relationship("ChatSession", back_populates="owner", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    title = Column(String, default="New Chat")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    
    # Relationships
    owner = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="chat_session", cascade="all, delete-orphan")
    documents = relationship(
        "Document",
        secondary=interaction_document_association,
        back_populates="interactions"
    )

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    chat_id = Column(Uuid, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    chat_session = relationship("ChatSession", back_populates="messages")

class Document(Base):
    __tablename__ = "documents"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False, index=True)
    source_type = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner_id = Column(Uuid, ForeignKey("users.id"), nullable=False)

    # Relationships
    owner = relationship("User", back_populates="documents")
    interactions = relationship(
        "ChatSession",
        secondary=interaction_document_association,
        back_populates="documents"
    )