from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from .core.config import settings

# Create async engine for Supabase PostgreSQL
engine = create_async_engine(
    settings.database_url,
    echo=False
)

# Create async session maker
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

# Async dependency for our API routes
async def get_db():
    """
    An async dependency function that yields a new database session for each request
    and ensures it's closed afterward.
    """
    async with AsyncSessionLocal() as session:
        yield session