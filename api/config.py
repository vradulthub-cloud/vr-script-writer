"""
Centralized configuration for the Eclatech Hub API.

Replaces scattered os.environ.get() calls and hardcoded sheet IDs
across asset_tracker.py, ticket_tools.py, notification_tools.py,
approval_tools.py, auth_config.py, call_sheet.py, and script_writer_app.py.

All values come from environment variables with sensible defaults
for the production Windows deployment.
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """App settings loaded from environment variables and .env file."""

    # --- Paths ---
    base_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent,
        description="Root of the Scripts directory (parent of api/)",
    )

    @property
    def service_account_file(self) -> Path:
        return self.base_dir / "service_account.json"

    @property
    def sqlite_db_path(self) -> Path:
        return self.base_dir / "eclatech_hub.db"

    # --- Google Sheet IDs ---
    grail_sheet_id: str = "1Eq5G5FU6A8EqeFZCnZjrEaMYS8F1DiK5vP5tCSINeJk"
    scripts_sheet_id: str = "1cY-8zNHLmD-oWdyEa2Mt3VY3nsFXHLEeZx0n42uf3ZQ"
    tickets_sheet_id: str = "1t92DvQxZzgHKjp4-uxaPLdyaqlmcGNLxSd6qx8hANyA"
    budgets_sheet_id: str = "1bM1G49p2KK9WY3WfjzPixrWUw8KBiDGKR-0jKw5QUVc"
    booking_sheet_id: str = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
    comp_planning_sheet_id: str = "1i6W4eZ8Bva3HvVmhpAVgjeHwfqbARkwBZ38aUhriaGs"

    # --- Google OAuth (for user auth, not service account) ---
    google_client_id: str = ""
    google_client_secret: str = ""

    # --- API Keys ---
    anthropic_api_key: str = ""
    fal_key: str = ""

    # --- Email Notifications ---
    ticket_notify_email: str = ""
    ticket_notify_password: str = ""

    # --- Ollama ---
    ollama_base_url: str = "http://localhost:11434/v1"

    # --- ComfyUI (Windows box, FLUX local title generation) ---
    comfyui_host: str = "http://100.90.90.68:8188"
    comfyui_timeout_seconds: int = 120

    # --- Sync Engine ---
    sheets_sync_interval_seconds: int = 300  # 5 minutes

    # --- Grail Tab Names (studio name mapping) ---
    grail_tabs: dict[str, str] = {
        "FuckPassVR": "FPVR",
        "VRHush": "VRH",
        "VRAllure": "VRA",
        "NaughtyJOI": "NNJOI",
    }

    # --- Studio Branding ---
    studio_site_codes: dict[str, str] = {
        "FuckPassVR": "fpvr",
        "VRHush": "vrh",
        "VRAllure": "vra",
        "NaughtyJOI": "njoi",
    }

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance. Cached for process lifetime."""
    return Settings()
