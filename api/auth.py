"""
Google OAuth authentication for the FastAPI backend.

Validates Google OAuth tokens and maps users to roles/permissions
from the users table (synced from the Tickets sheet "Users" tab).

Provides FastAPI dependency injection for:
  - get_current_user: validates token, returns user dict
  - require_admin: ensures user has admin role
  - require_grail_writer: ensures user can write to Grail
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from api.database import get_db

_log = logging.getLogger(__name__)

# Users with Grail write permission (title, categories, tags)
GRAIL_WRITERS = {"Drew", "David", "Duc"}
# Users with user management permission
USER_MANAGERS = {"Drew", "David"}


async def get_current_user(request: Request) -> dict:
    """
    Validate the Google OAuth token from the Authorization header.

    Returns a user dict with: email, name, role, allowed_tabs.
    Raises 401 if token is invalid or user not in the system.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = auth_header[7:]  # Strip "Bearer "

    try:
        # Verify the Google ID token
        idinfo = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
        )
        email = idinfo.get("email", "").lower()
    except Exception as exc:
        _log.warning("Token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Look up user in the local database
    with get_db() as conn:
        row = conn.execute(
            "SELECT name, role, allowed_tabs FROM users WHERE LOWER(email) = ?",
            (email,),
        ).fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User {email} not authorized",
        )

    return {
        "email": email,
        "name": dict(row)["name"],
        "role": dict(row)["role"],
        "allowed_tabs": dict(row)["allowed_tabs"],
    }


# Type alias for dependency injection
CurrentUser = Annotated[dict, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> dict:
    """Ensure the current user has admin role."""
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def require_grail_writer(user: CurrentUser) -> dict:
    """Ensure the current user can write to Grail (title/cats/tags)."""
    if user["name"] not in GRAIL_WRITERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Grail write access required",
        )
    return user


async def require_user_manager(user: CurrentUser) -> dict:
    """Ensure the current user can manage other users."""
    if user["name"] not in USER_MANAGERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User management access required",
        )
    return user
