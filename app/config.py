"""Application configuration settings."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    APP_NAME: str = "CSV Upload API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite:///./expense_calculator.db"
    
    # Upload settings
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: set[str] = {".csv"}
    
    # Special file patterns that require extra columns
    SPECIAL_FILE_PATTERN: str = "3005_statement"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
