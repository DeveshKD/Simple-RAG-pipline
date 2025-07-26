from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .core.config import settings

engine = create_engine(
    settings.database_url, connect_args={"check_same_thread": False}
)

# Each instance of SessionLocal will be a database session.
# The class itself is not a session yet.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# will inherit from this class to create each of the database models (ORM models).
Base = declarative_base()

# Dependency for our API routes
def get_db():
    """
    A dependency function that yields a new database session for each request
    and ensures it's closed afterward.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()