"""Integrations admin router — manages app-wide integration settings.

All endpoints here are admin-only. Right now this manages the Microsoft
Teams webhook URL (used by the notification dispatcher to broadcast events
to a Teams channel) and the hub_base_url used for Teams card links.

Routes:
  GET    /api/integrations/teams           — current webhook URL (masked) + status
  PUT    /api/integrations/teams           — set/update the webhook URL
  POST   /api/integrations/teams/test      — send a test message to verify the webhook
  GET    /api/integrations/hub-base-url    — base URL used in external messages
  PUT    /api/integrations/hub-base-url    — update the base URL
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from api.auth import CurrentUser
from api.database import get_db
from api import teams_webhook

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def _require_admin(user: dict) -> None:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")


def _mask_url(url: str) -> str:
    """Return a redacted preview of the webhook URL — safe to render in
    the admin UI without leaking the whole secret."""
    if not url:
        return ""
    if len(url) <= 32:
        return url[:8] + "…"
    return url[:24] + "…" + url[-6:]


# ---------------------------------------------------------------------------
# Teams webhook
# ---------------------------------------------------------------------------

class TeamsWebhookUpdate(BaseModel):
    url: str = Field(..., description="Power Automate Workflows or legacy Incoming Webhook URL. Empty string disables Teams.")


@router.get("/teams")
async def get_teams(user: CurrentUser):
    _require_admin(user)
    url = teams_webhook.get_webhook_url()
    with get_db() as conn:
        row = conn.execute(
            "SELECT updated_by, updated_at FROM app_settings WHERE key = 'teams_webhook_url'",
        ).fetchone()
    return {
        "configured": bool(url),
        "url_preview": _mask_url(url),
        "updated_by": (row["updated_by"] if row else "") or "",
        "updated_at": (row["updated_at"] if row else "") or "",
    }


_TEAMS_HOST_HINTS = (
    "webhookb2",
    "logic.azure.com",
    "outlook.office",
    "azureconnectors.com",
)


@router.put("/teams")
async def update_teams(req: TeamsWebhookUpdate, user: CurrentUser):
    _require_admin(user)
    url = req.url.strip()
    if url:
        if not url.startswith("https://"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL must start with https://",
            )
        if not any(h in url.lower() for h in _TEAMS_HOST_HINTS):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL doesn't look like a Teams/Power Automate webhook. Expected outlook.office.com, *.azureconnectors.com, or *.logic.azure.com.",
            )
    teams_webhook.set_webhook_url(url, updated_by=user.get("name", ""))
    _log.info("Teams webhook URL updated by %s (configured=%s)", user.get("name"), bool(url))
    return {"configured": bool(url), "url_preview": _mask_url(url)}


@router.post("/teams/test")
async def test_teams(user: CurrentUser):
    _require_admin(user)
    ok, err = teams_webhook.send_test(updated_by=user.get("name", ""))
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=err or "Teams webhook send failed",
        )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Hub base URL (used to build absolute links in Teams/email messages)
# ---------------------------------------------------------------------------

class HubBaseUrlUpdate(BaseModel):
    url: str = Field(..., description="Absolute URL of the hub frontend, e.g. https://eclatech-hub.vercel.app")


@router.get("/hub-base-url")
async def get_hub_base_url(user: CurrentUser):
    _require_admin(user)
    with get_db() as conn:
        row = conn.execute(
            "SELECT value, updated_by, updated_at FROM app_settings WHERE key = 'hub_base_url'",
        ).fetchone()
    return {
        "url": (row["value"] if row else "") or "",
        "updated_by": (row["updated_by"] if row else "") or "",
        "updated_at": (row["updated_at"] if row else "") or "",
    }


@router.put("/hub-base-url")
async def update_hub_base_url(req: HubBaseUrlUpdate, user: CurrentUser):
    _require_admin(user)
    url = req.url.strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must start with http:// or https://",
        )
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_by, updated_at)
            VALUES ('hub_base_url', ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            ON CONFLICT(key) DO UPDATE SET
              value = excluded.value,
              updated_by = excluded.updated_by,
              updated_at = excluded.updated_at
            """,
            (url, user.get("name", "")),
        )
    return {"url": url}
