import os
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Application settings
    app_name: str = "Meeting Minutes Transcription API"
    app_version: str = "1.0.0"
    debug: bool = os.environ.get("DEBUG", "False").lower() == "true"
    port: int = int(os.environ.get("PORT", "5001"))

    # Service URLs
    whisper_service_url: str = os.environ.get("WHISPER_SERVICE_URL", "http://whisper_service:8000")
    vllm_server_url: str = os.environ.get("VLLM_SERVER_URL", "http://vllm_service:8000")
    llm_uri: str = f"{vllm_server_url}/v1/chat/completions"

    # Redis settings
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # Security settings
    jwt_secret: str = os.environ.get("JWT_SECRET", "meeting_minutes_transcription_2024_secure_key")
    jwt_algorithm: str = os.environ.get("JWT_ALGORITHM", "HS256")

    # Model settings
    vllm_model: str = os.environ.get("VLLM_MODEL", "empty")
    assert vllm_model != "empty", "VLLM_MODEL is not set"

    # CORS settings
    cors_origins: list = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list = ["*"]
    cors_allow_headers: list = ["*"]

    class Config:
        env_file = ".env"
        extra = "allow"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

# Create and export the settings instance
settings = get_settings()
