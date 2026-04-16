"""
Users API router.

Provides endpoints for user profile and user management:
  GET    /api/users/me       — get current user profile (role, allowed_tabs)
  GET    /api/users/         — list all users (user-manager only)
  PATCH  /api/users/{email}  — update user role/tabs (user-manager only)
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from api.auth import CurrentUser, require_user_manager
from api.database import get_db
from api.sheets_client import open_tickets, get_or_create_worksheet, with_retry

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class UserUpdate(BaseModel):
    role: Optional[str] = None
    allowed_tabs: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/me")
async def get_me(user: CurrentUser):
    """Return the current user's profile: email, name, role, allowed_tabs."""
    return {
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "allowed_tabs": user["allowed_tabs"],
    }


@router.get("/")
async def list_users(user: CurrentUser):
    """List all users. Requires user-manager permission."""
    if user["name"] not in {"Drew", "David"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User management access required",
        )
    with get_db() as conn:
        rows = conn.execute(
            "SELECT email, name, role, allowed_tabs FROM users ORDER BY name"
        ).fetchall()
    return [dict(r) for r in rows]


@router.patch("/{email}")
async def update_user(email: str, body: UserUpdate, user: CurrentUser):
    """Update a user's role and/or allowed_tabs. Requires user-manager permission."""
    if user["name"] not in {"Drew", "David"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User management access required",
        )

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE LOWER(email) = ?",
            (email.lower(),),
        ).fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {email} not found",
            )

        updates = {}
        if body.role is not None:
            if body.role not in ("admin", "editor"):
                raise HTTPException(status_code=400, detail="Role must be 'admin' or 'editor'")
            updates["role"] = body.role
        if body.allowed_tabs is not None:
            updates["allowed_tabs"] = body.allowed_tabs

        if not updates:
            return dict(row)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [email.lower()]
        conn.execute(
            f"UPDATE users SET {set_clause} WHERE LOWER(email) = ?",
            vals,
        )

    # Fire-and-forget write to Google Sheets "Users" tab
    target = dict(row)
    target.update(updates)
    threading.Thread(
        target=_update_user_in_sheet,
        args=(email, target),
        daemon=True,
    ).start()

    return target


# ---------------------------------------------------------------------------
# Sheets write-through (background)
# ---------------------------------------------------------------------------

def _update_user_in_sheet(email: str, user_data: dict) -> None:
    """Update a user row in the Tickets sheet 'Users' tab."""
    try:
        sh = open_tickets()
        ws = get_or_create_worksheet(sh, "Users", headers=["Email", "Name", "Role", "Allowed Tabs"])
        rows = with_retry(lambda: ws.get_all_values())

        for i, row in enumerate(rows):
            if i == 0:
                continue  # Skip header
            if row and row[0].lower() == email.lower():
                row_num = i + 1  # 1-indexed
                with_retry(lambda rn=row_num: ws.update(
                    f"C{rn}:D{rn}",
                    [[user_data.get("role", ""), user_data.get("allowed_tabs", "")]],
                ))
                _log.info("Updated user %s in Sheets (row %d)", email, row_num)
                return

        _log.warning("User %s not found in Sheets — skipping write-through", email)
    except Exception:
        _log.exception("Failed to write user update to Sheets for %s", email)
