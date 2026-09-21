"""Centralised configuration loaded from .env and environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings:
    """Application settings dynamically reflecting environment variables."""

    def __init__(self):
        load_dotenv(_ENV_PATH, override=True)

    @property
    def ipf_url(self) -> str:
        return os.getenv("IPF_URL", "")

    @property
    def ipf_token(self) -> str:
        return os.getenv("IPF_TOKEN", "")

    @property
    def ipf_verify(self) -> bool:
        return os.getenv("IPF_VERIFY", "true").lower() == "true"

    @property
    def openrouter_api_key(self) -> str:
        return os.getenv("OPENROUTER_API_KEY", "")

    @property
    def openrouter_model(self) -> str:
        return os.getenv("OPENROUTER_MODEL", "antigravity/gemini-3.7-flash-tiered")

    @property
    def data_mode(self) -> str:
        return os.getenv("DATA_MODE", "demo").lower()

    @property
    def is_live(self) -> bool:
        return self.data_mode == "live"

    @property
    def has_llm(self) -> bool:
        return bool(self.openrouter_api_key)


settings = Settings()

