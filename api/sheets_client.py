"""
Consolidated Google Sheets client for the Eclatech Hub.

Replaces 6 duplicated _cached_client / _get_client() patterns across:
  - asset_tracker.py
  - ticket_tools.py
  - notification_tools.py
  - approval_tools.py
  - auth_config.py
  - script_writer_app.py

Provides:
  - Single cached gspread client (30-min TTL)
  - Unified retry logic with exponential backoff on 429 errors
  - Typed sheet accessors for all 6 Google Sheets
  - Worksheet-level caching with auto-invalidation
"""

from __future__ import annotations

import logging
import time
import threading
from typing import Any, Callable, TypeVar

import gspread
from google.oauth2.service_account import Credentials

from api.config import get_settings

_log = logging.getLogger(__name__)

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Scopes — superset of all modules (Sheets + Drive for call_sheet/docs)
# ---------------------------------------------------------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]

# ---------------------------------------------------------------------------
# Client cache — single instance, thread-safe, 30-min TTL
# ---------------------------------------------------------------------------
_CLIENT_TTL = 1800  # 30 minutes

_lock = threading.Lock()
_client: gspread.Client | None = None
_client_at: float = 0


def get_client() -> gspread.Client:
    """
    Return a cached gspread client (30-min TTL).

    Thread-safe. On expiry, creates a new client from the service account
    file and resets the timestamp.
    """
    global _client, _client_at

    now = time.time()
    if _client and (now - _client_at) < _CLIENT_TTL:
        return _client

    with _lock:
        # Double-check after acquiring lock
        now = time.time()
        if _client and (now - _client_at) < _CLIENT_TTL:
            return _client

        settings = get_settings()
        creds = Credentials.from_service_account_file(
            str(settings.service_account_file),
            scopes=SCOPES,
        )
        _client = gspread.authorize(creds)
        _client_at = now
        _log.debug("Sheets client refreshed (TTL=%ds)", _CLIENT_TTL)
        return _client


def invalidate_client() -> None:
    """Force the next get_client() call to create a fresh client."""
    global _client, _client_at
    with _lock:
        _client = None
        _client_at = 0


# ---------------------------------------------------------------------------
# Retry with exponential backoff on 429 rate-limit errors
# ---------------------------------------------------------------------------
def with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int = 4,
    base_sleep: float = 3,
) -> T:
    """
    Call fn(), retrying on Google Sheets 429 (quota-exceeded) errors.

    Uses exponential backoff: 3s, 6s, 12s, 24s by default.
    Raises the original exception after all retries exhausted.
    """
    for attempt in range(max_retries):
        try:
            return fn()
        except gspread.exceptions.APIError as exc:
            if "429" in str(exc) and attempt < max_retries - 1:
                wait = base_sleep * (2 ** attempt)
                _log.warning(
                    "Sheets 429 — waiting %.0fs (attempt %d/%d)",
                    wait,
                    attempt + 1,
                    max_retries,
                )
                time.sleep(wait)
            else:
                raise
    # Should never reach here, but satisfy type checker
    raise RuntimeError("with_retry exhausted all attempts")


# ---------------------------------------------------------------------------
# Sheet accessors — typed convenience for all 6 sheets
# ---------------------------------------------------------------------------
def open_grail() -> gspread.Spreadsheet:
    """Open the Grail master sheet (scene metadata)."""
    s = get_settings()
    return with_retry(lambda: get_client().open_by_key(s.grail_sheet_id))


def open_scripts() -> gspread.Spreadsheet:
    """Open the Scripts sheet (monthly script inventory)."""
    s = get_settings()
    return with_retry(lambda: get_client().open_by_key(s.scripts_sheet_id))


def open_tickets() -> gspread.Spreadsheet:
    """Open the Tickets sheet (tickets + users + notifications)."""
    s = get_settings()
    return with_retry(lambda: get_client().open_by_key(s.tickets_sheet_id))


def open_budgets() -> gspread.Spreadsheet:
    """Open the Budgets sheet (monthly shoot budgets)."""
    s = get_settings()
    return with_retry(lambda: get_client().open_by_key(s.budgets_sheet_id))


def open_booking() -> gspread.Spreadsheet:
    """Open the Booking sheet (model rates & agencies)."""
    s = get_settings()
    return with_retry(lambda: get_client().open_by_key(s.booking_sheet_id))


def open_comp_planning() -> gspread.Spreadsheet:
    """Open the Comp Planning sheet (compilation scene selection)."""
    s = get_settings()
    return with_retry(lambda: get_client().open_by_key(s.comp_planning_sheet_id))


def open_revenue() -> gspread.Spreadsheet:
    """Open the Premium Breakdowns sheet (revenue per platform/scene/month)."""
    s = get_settings()
    return with_retry(lambda: get_client().open_by_key(s.revenue_sheet_id))


# ---------------------------------------------------------------------------
# Worksheet helpers — get-or-create with optional header init
# ---------------------------------------------------------------------------
def get_or_create_worksheet(
    spreadsheet: gspread.Spreadsheet,
    tab_name: str,
    *,
    headers: list[str] | None = None,
    rows: int = 500,
) -> gspread.Worksheet:
    """
    Get a worksheet by name, creating it if missing.

    If `headers` is provided and the first row is empty or doesn't match,
    writes the header row, bolds it, and freezes row 1.
    """
    try:
        ws = spreadsheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        cols = len(headers) if headers else 26
        ws = spreadsheet.add_worksheet(title=tab_name, rows=rows, cols=cols)

    if headers:
        first_row = with_retry(lambda: ws.row_values(1))
        if not first_row or first_row[0] != headers[0]:
            col_letter = chr(ord("A") + len(headers) - 1)
            ws.update(f"A1:{col_letter}1", [headers])
            ws.format(f"A1:{col_letter}1", {"textFormat": {"bold": True}})
            ws.freeze(rows=1)

    return ws


# ---------------------------------------------------------------------------
# Bulk data fetch — read all rows from a worksheet
# ---------------------------------------------------------------------------
def fetch_all_rows(
    ws: gspread.Worksheet,
    *,
    include_header: bool = False,
) -> list[list[str]]:
    """
    Fetch all rows from a worksheet with retry.

    Returns list of row lists. Skips header row by default.
    """
    rows = with_retry(lambda: ws.get_all_values())
    if not include_header and rows:
        return rows[1:]
    return rows


def fetch_as_dicts(ws: gspread.Worksheet) -> list[dict[str, Any]]:
    """Fetch all rows as dicts (header row becomes keys) with retry."""
    return with_retry(lambda: ws.get_all_records())
