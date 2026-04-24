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
    azure_api_key: Optional[str] = None
    azure_api_base: Optional[str] = None
    aws_bearer_token_bedrock: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    openrouter_api_base: Optional[str] = None
    fireworks_ai_api_key: Optional[str] = None
    litellm_proxy_api_key: Optional[str] = None
    litellm_proxy_api_base: Optional[str] = None

    # Web Search (Serper API)
    serper_api_key: Optional[str] = None

    # LLM Retry and Rate Limiting
    llm_num_retries: int = 5  # Number of retries for 429/503/timeout errors
    llm_max_concurrent: int = 5  # Max concurrent async LLM calls (prevents rate limiting)
    batch_max_concurrent_jobs: int = 3  # Max QA jobs processed in parallel within a batch
    batch_max_concurrent_claims: int = 5  # Max claims checked/scored in parallel per job
    batch_max_concurrent_scorers_per_job: int = 2  # Accuracy + rubric scorers within one QA job

    # Langfuse Observability (optional)
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_base_url: Optional[str] = None  # Defaults to Langfuse cloud if not set

    # Auth Settings
    jwt_secret_key: str  # Required - set in .env
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 4320  # 3 days
    admin_api_key: str  # Required - for creating users via API

    # Extensions (comma-separated list, e.g. "aibots,custom")
    kaleidoscope_extensions: str = ""

    # Generation Defaults
    default_persona_count: int = 5
    default_question_count: int = 10

    # Question type/scope distribution ratios
    question_ratios_with_kb: dict = {
        ("typical", "in_kb"): 0.70,
        ("typical", "out_kb"): 0.10,
        ("edge", "in_kb"): 0.15,
        ("edge", "out_kb"): 0.05,
    }
    question_ratios_no_kb: dict = {
        ("typical", "out_kb"): 0.80,
        ("edge", "out_kb"): 0.20,
    }

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
