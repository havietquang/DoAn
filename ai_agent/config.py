import os
import logging
from typing import Optional
from pydantic import BaseSettings, validator


logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Database settings
    postgres_host: str = os.getenv("POSTGRES_HOST", "postgres")
    postgres_port: str = os.getenv("POSTGRES_PORT", "5432")
    postgres_db: str = os.getenv("POSTGRES_DB", "olist_dw")
    postgres_user: str = os.getenv("POSTGRES_USER", "olist_user")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "olist_pass")

    # OpenAI settings
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # API settings
    api_host: str = os.getenv("AI_AGENT_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("AI_AGENT_PORT", "8000"))

    # Additional settings
    debug_mode: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Validation
    @validator('postgres_port')
    def validate_postgres_port(cls, v):
        try:
            port = int(v)
            if not (1024 <= port <= 65535):
                raise ValueError("Port must be between 1024 and 65535")
            return str(port)
        except ValueError:
            raise ValueError("Invalid port number")

    @validator('api_port')
    def validate_api_port(cls, v):
        if not (1024 <= v <= 65535):
            raise ValueError("API port must be between 1024 and 65535")
        return v

    @validator('openai_model')
    def validate_openai_model(cls, v):
        valid_models = ["gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
        if v not in valid_models:
            logger.warning(f"Model {v} not in known valid models: {valid_models}")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False


# Create settings instance
settings = Settings()

# Configure logging based on settings
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='[%(asctime)s] %(levelname)s - %(name)s: %(message)s'
)

# Log configuration (without sensitive data)
logger.info("Configuration loaded:")
logger.info(f"  Database: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
logger.info(f"  OpenAI Model: {settings.openai_model}")
logger.info(f"  API: {settings.api_host}:{settings.api_port}")
logger.info(f"  Debug Mode: {settings.debug_mode}")
logger.info(f"  OpenAI API Key: {'Set' if settings.openai_api_key else 'Not set'}")
