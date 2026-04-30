from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Project-level runtime settings.

    Values are loaded in this order, with later sources overriding earlier ones:
      1. Defaults defined here
      2. A .env file in the project root (if it exists)
      3. Environment variables set in your shell

    Add project-specific settings below as typed fields.
    Keep secrets (API keys, passwords, connection strings) in .env only —
    never hardcode them here or in notebooks.
    """

    model_config = SettingsConfigDict(
        # Look for a .env file at the project root
        env_file=".env",
        # Don't crash if .env doesn't exist — it's optional
        env_file_encoding="utf-8",
        # Ignore any env vars not defined as fields here
        extra="ignore",
    )

    # --- Environment ---

    # Controls debug output and logging verbosity throughout the project
    # Set to "production" in any shared or scheduled run environment
    environment: str = Field(default="development")

    # --- AI-template client settings ---
    # These configure tonedef.client, which routes production LLM calls through
    # LiteLLM/Instructor while keeping the current Anthropic backend selectable.
    provider_primary: str = Field(default="anthropic")
    default_model: str = Field(default="anthropic/claude-sonnet-4-5-20250929")
    eval_judge_model: str = Field(default="anthropic/claude-sonnet-4-5-20250929")
    eval_judge_pinned: bool = Field(default=True)

    max_tokens: int = Field(default=4096, ge=1)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    request_timeout_seconds: float = Field(default=60.0, gt=0.0)
    retry_max_attempts: int = Field(default=3, ge=1)

    cache_enabled: bool = Field(default=True)
    cache_dir: Path = Field(default=Path("cache"))

    trace_enabled: bool = Field(default=False)
    trace_backend: str = Field(default="none")

    cost_budget_usd: float = Field(default=5.0, ge=0.0)
    latency_budget_seconds: float = Field(default=30.0, gt=0.0)
    phase2_prompt_budget_tokens: int = Field(default=45000, ge=1)
    phase2_prompt_cache_enabled: bool = Field(default=False)

    # Set a fixed random seed for reproducibility
    random_seed: int = Field(default=42)

    # --- Paths ---
    # Directory containing Guitar Rig 7 factory presets (.ngrr files)
    # Leave empty if not available; build scripts will exit with a clear message
    gr7_presets_dir: str = Field(default="")

    # --- Logging ---
    # Controls file handler level; stderr is always WARNING+
    log_level: str = Field(default="INFO")

    # --- Secrets ---
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    google_api_key: SecretStr = Field(default=SecretStr(""))
    cohere_api_key: SecretStr = Field(default=SecretStr(""))
    langfuse_public_key: SecretStr = Field(default=SecretStr(""))
    langfuse_secret_key: SecretStr = Field(default=SecretStr(""))
    logfire_token: SecretStr = Field(default=SecretStr(""))
    phoenix_collector_endpoint: str = Field(default="")

    # --- LLM temperature ---
    # Phase 1 (sonic analysis): moderate for creative flexibility
    phase1_temperature: float = Field(default=0.4)
    # Phase 2 (component mapping): moderate for expressive chain design
    phase2_temperature: float = Field(default=0.35)

    # --- Exemplar matching weights ---
    # Structured scoring: tag overlap vs component name overlap
    exemplar_tag_weight: float = Field(default=0.6)
    exemplar_component_weight: float = Field(default=0.4)


# A single shared instance for import throughout the project
# Usage: from tonedef.settings import settings
settings = Settings()
