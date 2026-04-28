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

import hashlib
import logging
import threading
import time
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from api.database import get_db

_log = logging.getLogger(__name__)

# Users with Grail write permission (title, categories, tags)
GRAIL_WRITERS = {"Drew", "David", "Duc"}
# Users with user management permission
USER_MANAGERS = {"Drew", "David"}


# ---------------------------------------------------------------------------
# Verified-token TTL cache
# ---------------------------------------------------------------------------
# Every API call goes through this validator. Without a cache the JWT signature
# verify + DB user lookup runs N times per dashboard render (one per fetcher).
# With a 60s TTL keyed on a sha256 of the raw token, the same user's burst of
# requests after a token rotation skips both verify and DB lookup. The 60s
# window is well below the typical Google ID token lifetime (~1h), so revoked
# tokens still expire within a minute of the change reaching us — acceptable
# for a 7-person internal tool.
#
# Tokens are hashed before being used as keys so the raw JWT never sits in a
# long-lived dict. Cache size is bounded so a runaway client can't OOM us.
_TOKEN_CACHE: dict[str, tuple[float, dict]] = {}
_TOKEN_CACHE_LOCK = threading.Lock()
_TOKEN_CACHE_TTL = 60.0
_TOKEN_CACHE_MAX = 512


def _token_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> dict | None:
    now = time.time()
    with _TOKEN_CACHE_LOCK:
        entry = _TOKEN_CACHE.get(key)
        if entry is None:
            return None
        expires_at, user = entry
        if expires_at < now:
            # Expired — drop it so we don't grow the dict with stale entries.
            _TOKEN_CACHE.pop(key, None)
            return None
        return user


def _cache_put(key: str, user: dict) -> None:
    expires_at = time.time() + _TOKEN_CACHE_TTL
    with _TOKEN_CACHE_LOCK:
        # Bounded eviction: when the cache is full, drop the oldest expiring
        # entry. Cheaper than a full LRU and good enough for ~10s of users.
        if len(_TOKEN_CACHE) >= _TOKEN_CACHE_MAX and key not in _TOKEN_CACHE:
            oldest = min(_TOKEN_CACHE, key=lambda k: _TOKEN_CACHE[k][0])
            _TOKEN_CACHE.pop(oldest, None)
        _TOKEN_CACHE[key] = (expires_at, user)


def _cache_invalidate_user(email: str) -> None:
    """Drop every cached token entry for a given user. Called when a user's
    role/permissions change so they don't keep stale access for up to 60s."""
    email_lower = email.lower()
    with _TOKEN_CACHE_LOCK:
        for key in [k for k, (_, u) in _TOKEN_CACHE.items() if u.get("email") == email_lower]:
            _TOKEN_CACHE.pop(key, None)


async def _validate_token(token: str) -> dict:
    """
    Core token validation logic shared by get_current_user and
    validate_sse_token.  Accepts a raw JWT string (no "Bearer " prefix).

    Returns a user dict with: email, name, role, allowed_tabs.
    Raises 401/403 on failure.

    Caches successful validations for 60s keyed on sha256(token). Failures are
    not cached — a transient verify error shouldn't lock a user out for a
    minute, and a permanently bad token is cheap to keep rejecting.
    """
    cache_key = _token_key(token)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
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

    user = {
        "email": email,
        "name": dict(row)["name"],
        "role": dict(row)["role"],
        "allowed_tabs": dict(row)["allowed_tabs"],
    }
    _cache_put(cache_key, user)
    return user


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
    return await _validate_token(token)


async def validate_sse_token(
    request: Request,
    token: Optional[str] = None,
) -> dict:
    """
    Auth helper for SSE endpoints, where EventSource cannot set custom headers.

    Accepts the JWT from either:
      - The standard Authorization: Bearer <jwt> header, OR
      - A `token` query parameter (?token=<jwt>)

    The query-param path is the primary SSE path; the header path is kept for
    completeness and testing.  Raises 401/403 on failure.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        raw_token = auth_header[7:]
    elif token:
        raw_token = token
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token — provide Authorization header or ?token= query param",
        )
    return await _validate_token(raw_token)


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
