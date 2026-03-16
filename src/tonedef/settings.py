from __future__ import annotations

from pydantic import Field
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

    # --- Analysis parameters ---
    # Move project-specific thresholds and parameters here as they emerge
    # Example fields are shown below — remove or replace them

    # Standard significance threshold for hypothesis tests in this project
    alpha: float = Field(default=0.05)

    # Minimum observations required before running statistical tests
    min_sample_size: int = Field(default=30)

    # Set a fixed random seed for reproducibility
    random_seed: int = Field(default=42)


# A single shared instance for import throughout the project
# Usage: from {{ package_name }}.settings import settings
settings = Settings()
