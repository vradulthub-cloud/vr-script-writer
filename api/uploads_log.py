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


_TAIL_CHUNK = 4096


def _tail_lines(path: Path, n: int) -> list[str]:
    """Return up to ``n`` last lines of ``path`` without loading the whole file.

    Reads from the end in 4 KB chunks until enough newlines are collected.
    For a JSONL log that grows unboundedly this bounds read cost to O(n)
    instead of O(file size).
    """
    with path.open("rb") as fh:
        fh.seek(0, 2)
        size = fh.tell()
        if size == 0:
            return []
        buf = b""
        # +1 because the last newline terminates the final record; we want one
        # more boundary to be sure we captured a full line, not a tail fragment.
        needed = n + 1
        pos = size
        while pos > 0 and buf.count(b"\n") < needed:
            step = min(_TAIL_CHUNK, pos)
            pos -= step
            fh.seek(pos)
            buf = fh.read(step) + buf
    text = buf.decode("utf-8", errors="replace")
    lines = text.splitlines()
    return lines[-n:]


def read_recent(limit: int = 50) -> list[dict]:
    """Return the most recent ``limit`` rows, newest first. Tolerant of a
    missing file (returns ``[]``) and of malformed lines (skips them)."""
    path = _log_path()
    if not path.exists():
        return []
    with _lock:
        try:
            tail = _tail_lines(path, limit)
        except OSError as exc:
            _log.warning("uploads_log read failed: %s", exc)
            return []
    rows: list[dict] = []
    for line in reversed(tail):
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
