"""Centralised configuration loaded from .env and environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

DEFAULT_MODEL = "google/gemini-2.5-flash"


class Settings:
    """Application settings.

    DATA_MODE:
      - "live"      connect to an IP Fabric instance (IPF_URL / IPF_TOKEN) and read the selected snapshot.
      - "recorded"  read a JSON export previously recorded from a live IP Fabric snapshot (demo_data/recorded/).
                    Used for the hosted version, which cannot reach a local IP Fabric appliance.
      ("demo" is accepted as an alias for "recorded".)
    """

    def __init__(self):
        load_dotenv(_ENV_PATH, override=False)

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
        return os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)

    @property
    def data_mode(self) -> str:
        mode = os.getenv("DATA_MODE", "live").lower()
        return "recorded" if mode == "demo" else mode

    @property
    def is_live(self) -> bool:
        return self.data_mode == "live"

    @property
    def has_llm(self) -> bool:
        return bool(self.openrouter_api_key)


settings = Settings()
