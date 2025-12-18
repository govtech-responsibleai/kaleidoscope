"""
Configuration management for Kaleidoscope API.

Loads environment variables and provides centralized configuration access.
"""

from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache

MODEL_KEYWORDS_WITH_FIXED_TEMPERATURE = {"gpt-5"}

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Settings
    api_title: str = "Kaleidoscope API"
    api_version: str = "1.0.0"
    api_prefix: str = "/api/v1"

    # Database Settings
    database_url: str = "postgresql://localhost:5432/kaleidoscope"
    database_echo: bool = False  # Set to True for SQL query logging

    # LLM Settings
    default_llm_model: str = "gemini/gemini-2.5-flash-lite"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None  # For Gemini models and Vertex AI
    azure_ai_api_key: Optional[str] = None
    azure_ai_api_base: Optional[str] = None

    # LLM Retry and Rate Limiting
    llm_num_retries: int = 3  # Number of retries for 429/503/timeout errors
    llm_max_concurrent: int = 5  # Max concurrent async LLM calls (prevents rate limiting) 

    # Phoenix Observability (optional)
    phoenix_api_key: Optional[str] = None
    phoenix_collector_endpoint: Optional[str] = None

    # Generation Defaults
    default_persona_count: int = 5
    default_question_count: int = 10

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
