"""Settings read once from the environment (repo-root .env file)."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    mongodb_uri_app: SecretStr
    mongodb_uri_proposer: SecretStr
    mongodb_db: str = "fde_harness"

    openrouter_api_key: SecretStr | None = None
    llm_spend_limit_usd: float = 9.0
    voyage_api_key: SecretStr | None = None

    # Model IDs live here and nowhere else. Chosen at build time from the live
    # OpenRouter model list (see TASKS.md Phase 3), never from memory.
    # Picked 2026-09-26 from https://openrouter.ai/api/v1/models (price per 1M in/out).
    runtime_model: str = "openai/gpt-5.6-luna"  # mid-tier, $0.20 / $1.20
    strong_model: str = "anthropic/claude-sonnet-5"  # calibration + final comparison, $2 / $10
    proposer_model: str = "openai/gpt-5.6-luna"  # U1: proposer quality barely matters
    investigator_model: str = "openai/gpt-5.6-luna"
    # Atlas Automated Embedding (autoEmbed index); no client-side embedding code.
    embedding_model: str = "voyage-4"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
