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

from fastapi import APIRouter, Depends, HTTPException, status
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


class UserCreate(BaseModel):
    email: str
    name: str
    role: str = "editor"
    allowed_tabs: str = "ALL"


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
async def list_users(_manager: dict = Depends(require_user_manager)):
    """List all users. Requires user-manager permission."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT email, name, role, allowed_tabs FROM users ORDER BY name"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/teammates")
async def list_teammates(user: CurrentUser):
    """List teammates available for tagging/assigning on tickets, etc. Returns
    only name + email (no role/permissions). Available to any authenticated
    user — distinct from the user-manager-only list_users endpoint."""
    del user  # only auth check matters
    with get_db() as conn:
        rows = conn.execute(
            "SELECT email, name FROM users ORDER BY name"
        ).fetchall()
    return [dict(r) for r in rows]


@router.patch("/{email}")
async def update_user(
    email: str,
    body: UserUpdate,
    _manager: dict = Depends(require_user_manager),
):
    """Update a user's role and/or allowed_tabs. Requires user-manager permission."""

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

    # Drop any cached token entries for this user so the role/allowed_tabs
    # change takes effect on their very next request, not after the 60s TTL.
    from api.auth import _cache_invalidate_user
    _cache_invalidate_user(email)

    # Fire-and-forget write to Google Sheets "Users" tab
    target = dict(row)
    target.update(updates)
    threading.Thread(
        target=_update_user_in_sheet,
        args=(email, target),
        daemon=True,
    ).start()

    return target


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, _manager: dict = Depends(require_user_manager)):
    """Add a new user to the team. Requires user-manager permission."""
    if body.role not in ("admin", "editor"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'editor'")
    email = body.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Invalid email")

    with get_db() as conn:
        existing = conn.execute(
            "SELECT 1 FROM users WHERE LOWER(email) = ?", (email,),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"User {email} already exists")
        conn.execute(
            "INSERT INTO users (email, name, role, allowed_tabs) VALUES (?, ?, ?, ?)",
            (email, body.name.strip(), body.role, body.allowed_tabs),
        )

    user = {
        "email": email,
        "name": body.name.strip(),
        "role": body.role,
        "allowed_tabs": body.allowed_tabs,
    }
    threading.Thread(target=_append_user_to_sheet, args=(user,), daemon=True).start()
    _log.info("User %s created (role=%s)", email, body.role)
    return user


@router.delete("/{email}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(email: str, manager: dict = Depends(require_user_manager)):
    """Remove a user from the team. Requires user-manager permission."""
    target_email = email.lower()
    if target_email == manager["email"].lower():
        raise HTTPException(status_code=400, detail="You cannot remove yourself")

    with get_db() as conn:
        result = conn.execute(
            "DELETE FROM users WHERE LOWER(email) = ?", (target_email,),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"User {email} not found")

    # Revoke cached access immediately — without this the deleted user keeps
    # working for up to the token-cache TTL (60s) after their row is gone.
    from api.auth import _cache_invalidate_user
    _cache_invalidate_user(target_email)

    threading.Thread(target=_remove_user_from_sheet, args=(target_email,), daemon=True).start()
    _log.info("User %s deleted by %s", target_email, manager["email"])
    return None


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


def _append_user_to_sheet(user: dict) -> None:
    """Append a new user row to the Tickets sheet 'Users' tab."""
    try:
        sh = open_tickets()
        ws = get_or_create_worksheet(sh, "Users", headers=["Email", "Name", "Role", "Allowed Tabs"])
        with_retry(lambda: ws.append_row(
            [user["email"], user["name"], user["role"], user.get("allowed_tabs", "")],
            value_input_option="USER_ENTERED",
        ))
        _log.info("Appended user %s to Sheets", user["email"])
    except Exception:
        _log.exception("Failed to append user %s to Sheets", user["email"])


def _remove_user_from_sheet(email: str) -> None:
    """Delete a user row from the Tickets sheet 'Users' tab."""
    try:
        sh = open_tickets()
        ws = get_or_create_worksheet(sh, "Users", headers=["Email", "Name", "Role", "Allowed Tabs"])
        rows = with_retry(lambda: ws.get_all_values())
        for i, row in enumerate(rows):
            if i == 0:
                continue
            if row and row[0].lower() == email.lower():
                with_retry(lambda rn=i + 1: ws.delete_rows(rn))
                _log.info("Removed user %s from Sheets (row %d)", email, i + 1)
                return
        _log.warning("User %s not found in Sheets — skipping removal", email)
    except Exception:
        _log.exception("Failed to remove user %s from Sheets", email)
