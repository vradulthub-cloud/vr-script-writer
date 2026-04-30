"""uploads_log.py — append-only audit log for the Uploads dashboard.

Each completed upload writes one JSON line to ``uploads_log.jsonl`` next to
``mega_scan.json``. The Recent uploads panel on /uploads renders the most
recent N entries via ``read_recent``.

Lock-protected for the rare case of two completes landing simultaneously.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Iterable

_log = logging.getLogger(__name__)
_lock = threading.Lock()


def _log_path() -> Path:
    """Resolve the log file location.

    Mirrors the convention used elsewhere in the repo: writes sit next to the
    Python files on the deployment host. ``$UPLOADS_LOG_FILE`` overrides for
    tests.
    """
    override = os.environ.get("UPLOADS_LOG_FILE")
    if override:
        return Path(override)
    here = Path(__file__).resolve().parent.parent
    return here / "uploads_log.jsonl"


def append(entry: dict) -> None:
    """Append one upload to the log. ``entry`` should include at minimum
    ``user_email``, ``user_name``, ``studio``, ``scene_id``, ``subfolder``,
    ``filename``, ``key``, ``size``, ``mode``. ``ts`` is filled in if absent."""
    entry = dict(entry)  # don't mutate caller's dict
    entry.setdefault("ts", time.time())
    line = json.dumps(entry, separators=(",", ":"), default=str)
    path = _log_path()
    with _lock:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError as exc:
            _log.warning("uploads_log append failed: %s", exc)


def read_recent(limit: int = 50) -> list[dict]:
    """Return the most recent ``limit`` rows, newest first. Tolerant of a
    missing file (returns ``[]``) and of malformed lines (skips them)."""
    path = _log_path()
    if not path.exists():
        return []
    rows: list[dict] = []
    with _lock:
        try:
            with path.open("r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except OSError as exc:
            _log.warning("uploads_log read failed: %s", exc)
            return []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(rows) >= limit:
            break
    return rows


def truncate_to(keep: int) -> int:
    """Trim the log to the most recent ``keep`` rows. Returns rows kept.
    Useful for a periodic compaction cron — not called from request paths."""
    path = _log_path()
    if not path.exists():
        return 0
    rows = read_recent(limit=keep)
    rows.reverse()  # back to chronological order before rewrite
    with _lock:
        try:
            with path.open("w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r, separators=(",", ":"), default=str) + "\n")
        except OSError as exc:
            _log.warning("uploads_log truncate failed: %s", exc)
    return len(rows)
