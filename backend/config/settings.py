from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), extra="ignore")

    # Active combo — re-read on each request, no server restart needed
    mawrid_combo: str = "H1G"

    # Internal DB (SQLite dev → PostgreSQL prod, one var change)
    database_url: str = "sqlite+aiosqlite:///./mawrid.db"

    # Infrastructure
    redis_url: str = "redis://redis:6379/0"
    mlflow_tracking_uri: str = "http://mlflow:5000"

    # Azure Document Intelligence
    azure_di_endpoint: str = ""
    azure_di_key: str = ""
    azure_di_classifier_model_id: str = "mawrid-classifier-v1"
    azure_di_extractor_model_id: str = "mawrid-extractor-v1"

    # Frontier LLM keys (LiteLLM reads these from env automatically)
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    dashscope_api_key: str = ""
    openrouter_api_key: str = ""
    groq_api_key: str = ""

    # Ollama (L3 combo)
    ollama_base_url: str = "http://localhost:11434"

    # Oracle — stub only, read-only, training data pull, not in live pipeline
    oracle_dsn: str = ""
    oracle_user: str = ""
    oracle_password: str = ""

    # Upload
    max_upload_size_mb: int = 20

    # Schema password — if set, GET /api/schema requires X-Schema-Password header
    schema_password: str = ""

    # CORS — comma-separated extra origins (e.g. your Vercel URL)
    allowed_origins: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
