"""
auth_config.py
User management and role-based access control for Eclatech Hub.
Loads user config from the "Users" tab in the Eclatech Tickets Google Sheet.
"""

import os
import time
from google.oauth2.service_account import Credentials
import gspread

# ── Configuration ─────────────────────────────────────────────────────────────
USERS_SHEET_ID = "1t92DvQxZzgHKjp4-uxaPLdyaqlmcGNLxSd6qx8hANyA"
USERS_TAB_NAME = "Users"
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# All available tabs in display order
ALL_TABS = [
    ("Missing",        "⚠️ Missing"),
    ("Tickets",        "🎟️ Tickets"),
    ("Model Research", "Model Research"),
    ("Scripts",        "Scripts"),
    ("Call Sheets",    "Call Sheets"),
    ("Titles",         "Titles"),
    ("Descriptions",   "Descriptions"),
    ("Compilations",   "🎬 Compilations"),
]
ALL_TAB_KEYS = [key for key, _ in ALL_TABS]

# ── Sheet client (cached) ────────────────────────────────────────────────────
_cached_client = None
_cached_at = 0


def _get_client():
    global _cached_client, _cached_at
    now = time.time()
    if _cached_client and (now - _cached_at) < 1800:
        return _cached_client
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    _cached_client = gspread.authorize(creds)
    _cached_at = now
    return _cached_client


# ── User config loading ──────────────────────────────────────────────────────
_users_cache = None
_users_cache_at = 0
_USERS_CACHE_TTL = 300  # 5 minutes


def load_users_config():
    """
    Load user config from the Users sheet tab.
    Returns dict keyed by lowercase email:
    {
        "drew@gmail.com": {
            "name": "Drew",
            "role": "admin",
            "allowed_tabs": ["ALL"] or ["Scripts", "Tickets", ...]
        }
    }
    Cached for 5 minutes.
    """
    global _users_cache, _users_cache_at
    now = time.time()
    if _users_cache and (now - _users_cache_at) < _USERS_CACHE_TTL:
        return _users_cache

    gc = _get_client()
    sh = gc.open_by_key(USERS_SHEET_ID)
    ws = sh.worksheet(USERS_TAB_NAME)
    rows = ws.get_all_values()

    users = {}
    for row in rows[1:]:  # skip header
        if len(row) < 4 or not row[0].strip():
            continue
        email = row[0].strip().lower()
        name = row[1].strip()
        role = row[2].strip().lower()
        tabs_raw = row[3].strip()

        if tabs_raw.upper() == "ALL":
            allowed = list(ALL_TAB_KEYS)
        else:
            allowed = [t.strip() for t in tabs_raw.split(",") if t.strip()]

        users[email] = {
            "name": name,
            "role": role,
            "allowed_tabs": allowed,
        }

    _users_cache = users
    _users_cache_at = now
    return users


def get_user_permissions(email):
    """Look up user by email. Returns None if not authorized."""
    users = load_users_config()
    return users.get(email.lower())


def get_allowed_tabs(user_config):
    """Return list of (key, label) tuples for tabs this user can access."""
    if user_config["role"] == "admin":
        return list(ALL_TABS)
    allowed_keys = set(user_config["allowed_tabs"])
    return [(key, label) for key, label in ALL_TABS if key in allowed_keys]


def is_admin(user_config):
    """Check if user has admin role."""
    return user_config["role"] == "admin"


def invalidate_cache():
    """Force reload of user config on next access."""
    global _users_cache, _users_cache_at
    _users_cache = None
    _users_cache_at = 0
