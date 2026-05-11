"""
YahavisAI Backend Configuration
Production-ready settings with environment variable support
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "YahavisAI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"  # development, staging, production
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    
    # Security
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "https://jarvisai.app",
        "https://*.jarvisai.app"
    ]
    
    # Database - Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_JWT_SECRET: Optional[str] = None
    
    # Redis (for task queue and caching)
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: Optional[str] = None
    
    # AI APIs
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash-preview-05-20"
    GEMINI_TEMPERATURE: float = 0.7
    GEMINI_MAX_TOKENS: int = 4096
    
    # Whisper (Voice)
    OPENAI_API_KEY: Optional[str] = None  # For Whisper API fallback
    WHISPER_MODEL_SIZE: str = "base"  # tiny, base, small, medium, large
    
    # WebSocket
    WS_PING_INTERVAL: int = 20
    WS_PING_TIMEOUT: int = 20
    WS_MAX_MESSAGE_SIZE: int = 1024 * 1024  # 1MB
    
    # Automation
    N8N_WEBHOOK_URL: Optional[str] = None
    N8N_API_KEY: Optional[str] = None
    MAX_AUTOMATION_RETRIES: int = 3
    AUTOMATION_TIMEOUT_SECONDS: int = 300
    
    # Desktop Agent
    AGENT_HEARTBEAT_INTERVAL: int = 30
    AGENT_TIMEOUT_SECONDS: int = 60
    
    # File Upload
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50MB
    UPLOAD_DIR: str = "uploads"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings"""
    return settings


# Environment-specific overrides
def get_cors_origins() -> List[str]:
    """Get CORS origins based on environment"""
    if settings.ENVIRONMENT == "development":
        return ["*"]
    return settings.CORS_ORIGINS


def get_database_url() -> str:
    """Get PostgreSQL connection URL for SQLAlchemy (if needed alongside Supabase)"""
    # Extract from Supabase URL if needed
    return f"{settings.SUPABASE_URL}/rest/v1"
