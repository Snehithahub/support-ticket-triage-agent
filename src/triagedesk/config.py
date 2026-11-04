"""Typed configuration loaded from environment variables (and an optional .env file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

Provider = Literal["fake", "gemini", "groq", "openai", "azure", "custom"]

# Defaults per provider. Any of these can be overridden with LLM_BASE_URL / LLM_MODEL.
PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.5-flash",
        "embeddings_model": "gemini-embedding-001",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "embeddings_model": "text-embedding-3-small",
    },
    # Azure: LLM_BASE_URL is the resource endpoint and LLM_MODEL is the deployment name.
    "azure": {"base_url": "", "model": ""},
    "custom": {"base_url": "", "model": ""},
    "fake": {"base_url": "", "model": "fake-heuristic-v1"},
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://triagedesk:triagedesk@localhost:15433/triagedesk"
    db_pool_max: int = 10

    llm_provider: Provider = "fake"
    llm_base_url: str | None = None
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_timeout_s: float = 30.0
    llm_max_retries: int = 3
    llm_json_mode: bool = True
    azure_api_version: str = "2024-10-21"

    embeddings_provider: Literal["fastembed", "api", "hash"] = "fastembed"
    embeddings_model: str = "BAAI/bge-small-en-v1.5"
    embeddings_dim: int = 384
    embeddings_cache_dir: str | None = None

    kb_dir: Path = PROJECT_ROOT / "kb" / "articles"
    kb_base_url: str = "http://localhost:8401/kb"
    policy_path: Path = PROJECT_ROOT / "config" / "automation_policy.yaml"

    retrieval_top_k: int = 5
    retrieval_candidates: int = 20
    rrf_k: int = 60
    # Below this classifier confidence, retrieval is not filtered by intent.
    retrieval_filter_min_confidence: float = 0.5
    # Unfiltered hits merged into intent-filtered results (cross-category answers).
    retrieval_unfiltered_mix: int = 2

    classify_max_attempts: int = 3
    draft_max_attempts: int = 2
    grounding_min_support: float = 0.5

    log_level: str = "INFO"
    log_json: bool = True

    max_ticket_chars: int = Field(default=20_000, ge=100)

    @model_validator(mode="after")
    def _apply_preset(self) -> Settings:
        preset = PROVIDER_PRESETS[self.llm_provider]
        if not self.llm_base_url and preset["base_url"]:
            self.llm_base_url = preset["base_url"]
        if not self.llm_model and preset["model"]:
            self.llm_model = preset["model"]
        return self

    @property
    def demo_mode(self) -> bool:
        return self.llm_provider == "fake"

    def article_url(self, article_id: str) -> str:
        return f"{self.kb_base_url.rstrip('/')}/{article_id}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
