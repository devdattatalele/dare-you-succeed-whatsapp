"""
Configuration settings for WhatsApp BetTask Backend.

Loads environment variables and provides centralized configuration management.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator
import logging

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App configuration
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Supabase configuration
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    
    # WhatsApp MCP configuration (replaces webhook settings)
    WHATSAPP_MCP_BRIDGE_URL: str = "http://localhost:8080"
    WHATSAPP_MCP_DATABASE_PATH: str = "../whatsapp-mcp/whatsapp-bridge/store/messages.db"
    
    # Gemini AI configuration
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"
    
    # Server configuration
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    
    # Retry configuration
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # File upload limits
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_FILE_TYPES: list = ["image/jpeg", "image/png", "image/webp", "video/mp4"]
    
    # Reminder configuration
    REMINDER_CHECK_INTERVAL_MINUTES: int = 15
    DEFAULT_REMINDER_HOURS_BEFORE: int = 2
    
    # Database connection pool
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v.upper()
    
    @field_validator("SUPABASE_URL")
    @classmethod
    def validate_supabase_url(cls, v):
        """Validate Supabase URL format."""
        if not v.startswith("https://"):
            raise ValueError("SUPABASE_URL must start with https://")
        return v
    
    @field_validator("MAX_FILE_SIZE_MB")
    @classmethod
    def validate_file_size(cls, v):
        """Validate file size limit."""
        if v <= 0 or v > 50:
            raise ValueError("MAX_FILE_SIZE_MB must be between 1 and 50")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def get_database_url(self) -> str:
        """Get formatted database URL for direct connections."""
        return f"{self.SUPABASE_URL}/rest/v1/"
    
    def get_storage_url(self) -> str:
        """Get Supabase Storage URL."""
        return f"{self.SUPABASE_URL}/storage/v1"
    
    def get_auth_url(self) -> str:
        """Get Supabase Auth URL."""
        return f"{self.SUPABASE_URL}/auth/v1"
    
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.DEBUG and os.getenv("ENVIRONMENT", "development") == "production"
    
    def get_log_config(self) -> dict:
        """Get logging configuration."""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
                },
                "detailed": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s"
                }
            },
            "handlers": {
                "default": {
                    "level": self.LOG_LEVEL,
                    "formatter": "detailed" if self.DEBUG else "standard",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout"
                }
            },
            "loggers": {
                "": {
                    "handlers": ["default"],
                    "level": self.LOG_LEVEL,
                    "propagate": False
                }
            }
        }

# Global settings instance
settings = Settings()

# Validate required settings on import
def validate_required_settings():
    """Validate that all required settings are present."""
    required_settings = [
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY", 
        "SUPABASE_SERVICE_ROLE_KEY"
    ]
    
    missing_settings = []
    for setting in required_settings:
        if not getattr(settings, setting, None):
            missing_settings.append(setting)
    
    if missing_settings:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_settings)}\n"
            "Please check your .env file or environment configuration."
        )

# Validate on import
validate_required_settings() 