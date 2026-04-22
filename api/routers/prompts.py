"""
AI prompt overrides API router.

Lets admins read, edit, and revert the system prompts that drive
description / script / title generation. The bundled defaults live in
api/prompts.py; this router persists overrides in the SQLite
prompt_overrides table and exposes them alongside the defaults so the
admin UI can show diffs and revert with one click.

Endpoints:
  GET    /api/prompts/         — list every editable prompt with current text
  GET    /api/prompts/{key}    — single prompt
  PUT    /api/prompts/{key}    — save override (creates or updates)
  DELETE /api/prompts/{key}    — clear override (revert to bundled default)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.auth import require_admin
from api.database import get_db
from api.prompts import PROMPT_DEFAULTS, PROMPT_REGISTRY

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


class PromptEntry(BaseModel):
    key: str
    label: str
    group: str
    content: str            # active text (override if present, else default)
    default: str            # bundled default — for diffing in the UI
    is_overridden: bool
    updated_by: str = ""
    updated_at: str = ""


class PromptUpdate(BaseModel):
    content: str = Field(..., min_length=1)


def _load_overrides() -> dict[str, dict[str, str]]:
    """Pull all override rows into a {key: {content, updated_by, updated_at}} map."""
    out: dict[str, dict[str, str]] = {}
    with get_db() as conn:
        rows = conn.execute(
            "SELECT prompt_key, content, updated_by, updated_at FROM prompt_overrides"
        ).fetchall()
    for r in rows:
        d = dict(r)
        out[d["prompt_key"]] = {
            "content": d["content"],
            "updated_by": d.get("updated_by") or "",
            "updated_at": d.get("updated_at") or "",
        }
    return out


def _entry_for(meta: dict, overrides: dict[str, dict[str, str]]) -> PromptEntry:
    key = meta["key"]
    over = overrides.get(key)
    return PromptEntry(
        key=key,
        label=meta["label"],
        group=meta["group"],
        content=over["content"] if over else meta["default"],
        default=meta["default"],
        is_overridden=bool(over),
        updated_by=over["updated_by"] if over else "",
        updated_at=over["updated_at"] if over else "",
    )


@router.get("/", response_model=list[PromptEntry])
async def list_prompts(_admin: dict = Depends(require_admin)):
    """List every editable prompt with its current active text + default."""
    overrides = _load_overrides()
    return [_entry_for(meta, overrides) for meta in PROMPT_REGISTRY]


@router.get("/{key}", response_model=PromptEntry)
async def get_prompt_route(key: str, _admin: dict = Depends(require_admin)):
    meta = next((m for m in PROMPT_REGISTRY if m["key"] == key), None)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Unknown prompt key: {key}")
    overrides = _load_overrides()
    return _entry_for(meta, overrides)


@router.put("/{key}", response_model=PromptEntry)
async def upsert_prompt(
    key: str,
    body: PromptUpdate,
    user: dict = Depends(require_admin),
):
    """Save an override. Creates a row if one doesn't exist, replaces it if it does."""
    meta = next((m for m in PROMPT_REGISTRY if m["key"] == key), None)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Unknown prompt key: {key}")

    now = datetime.now(timezone.utc).isoformat()
    actor = user.get("name") or user.get("email") or "admin"
    with get_db() as conn:
        conn.execute(
            """INSERT INTO prompt_overrides (prompt_key, content, updated_by, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(prompt_key) DO UPDATE SET
                   content=excluded.content,
                   updated_by=excluded.updated_by,
                   updated_at=excluded.updated_at""",
            (key, body.content, actor, now),
        )

    overrides = _load_overrides()
    return _entry_for(meta, overrides)


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def revert_prompt(key: str, _admin: dict = Depends(require_admin)):
    """Drop the override row — get_prompt() then falls back to the bundled default."""
    if not any(m["key"] == key for m in PROMPT_REGISTRY):
        raise HTTPException(status_code=404, detail=f"Unknown prompt key: {key}")
    with get_db() as conn:
        conn.execute("DELETE FROM prompt_overrides WHERE prompt_key=?", (key,))
    return None
