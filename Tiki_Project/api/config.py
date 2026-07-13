# ============================================================
# CONFIGURATION - Environment Settings
# ============================================================

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file
    """
    
    # Gemini API
    GEMINI_API_KEY: str = Field(
        ...,
        alias="GEMINI_API_KEY",
        description="Google Gemini API Key"
    )
    
    # ChromaDB
    CHROMA_DB_PATH: str = Field(
        default=str(ROOT_DIR / "chroma_db"),
        alias="CHROMA_DB_PATH",
        description="Path to ChromaDB database directory"
    )
    
    # Data Path
    DATA_PATH: str = Field(
        default=str(ROOT_DIR / "data"),
        alias="DATA_PATH",
        description="Path to data directory"
    )
    
    # Models Path
    MODELS_PATH: str = Field(
        default=str(ROOT_DIR / "module"),
        alias="MODELS_PATH",
        description="Path to models directory"
    )
    
    # Embedding Model
    EMBEDDING_MODEL: str = Field(
        default="paraphrase-multilingual-mpnet-base-v2",
        alias="EMBEDDING_MODEL",
        description="Sentence-Transformers model name"
    )
    
    # API Server
    API_HOST: str = Field(
        default="0.0.0.0",
        alias="API_HOST",
        description="API server host"
    )
    
    API_PORT: int = Field(
        default=8000,
        alias="API_PORT",
        description="API server port"
    )
    
    # Logging
    LOG_LEVEL: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

# Create global settings instance
settings = Settings()
