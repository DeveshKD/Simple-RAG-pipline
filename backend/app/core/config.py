import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
ENV_PATH = os.path.join(project_root, '.env')

class Settings(BaseSettings):
    #jwt and auth
    secret_key: str = Field(..., validation_alias="SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    #database
    database_url: str = Field(..., validation_alias="SUPABASE_URL")
    supabase_api_key: str = Field(..., validation_alias="SUPABASE_API_KEY")

    #vector store
    chroma_db_path: str = Field(default="./backend/data/vector_store", validation_alias="CHROMA_DB_PATH")
    chroma_db_collection_name: str = Field(default="all_documents", validation_alias="CHROMA_DB_COLLECTION_NAME")

    #llm api
    google_genai_api_key: str = Field(..., validation_alias="GEMINI_API_KEY")
    google_genai_chat_model_id: str = Field(default="gemini-1.5-flash-latest", validation_alias="GOOGLE_GENAI_CHAT_MODEL_ID")
    google_genai_embedding_model_id: str = Field(default="gemini-embedding-exp-03-07", validation_alias="GOOGLE_GENAI_EMBEDDING_MODEL_ID")

    #common app settings
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    #sqlite
    #database_url: str = Field(default="sqlite:///./chat_database.db", validation_alias='DATABASE_URL')

    #project metadata
    project_name: str = "Multi-Tenant Visual RAG Platform"
    api_v1_prefix: str = "/api/v1"

    model_config = {
        "env_file": ENV_PATH,
        "env_file_encoding": 'utf-8',
        "case_sensitive": True,
        "extra": 'ignore'
    }


settings = Settings()


# Optional: Sanity checks and debug print
if not settings.google_genai_api_key or settings.google_genai_api_key.startswith("YOUR_"):
    print(f"Warning: GOOGLE_GENAI_API_KEY is not set correctly in {ENV_PATH}")
else:
    print(f"Loaded GOOGLE_GENAI_API_KEY: {settings.google_genai_api_key[:10]}...")

print(
    f"Loaded config: Port={settings.port}, LogLevel={settings.log_level}, "
    f"ChromaDB={settings.chroma_db_path}, Supabase={settings.database_url}"
)