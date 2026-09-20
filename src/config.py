"""Centralised configuration loaded from .env and environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH, override=True)


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    # IP Fabric
    ipf_url: str = field(default_factory=lambda: os.getenv("IPF_URL", ""))
    ipf_token: str = field(default_factory=lambda: os.getenv("IPF_TOKEN", ""))
    ipf_verify: bool = field(
        default_factory=lambda: os.getenv("IPF_VERIFY", "true").lower() == "true"
    )

    # OpenRouter
    openrouter_api_key: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_API_KEY", "")
    )
    openrouter_model: str = field(
        default_factory=lambda: os.getenv(
            "OPENROUTER_MODEL", "antigravity/gemini-3.7-flash-tiered"
        )
    )

    # Data mode
    data_mode: str = field(
        default_factory=lambda: os.getenv("DATA_MODE", "demo").lower()
    )

    @property
    def is_live(self) -> bool:
        return self.data_mode == "live"

    @property
    def has_llm(self) -> bool:
        return bool(self.openrouter_api_key)


settings = Settings()
