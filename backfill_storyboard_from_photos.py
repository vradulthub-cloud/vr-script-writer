"""backfill_storyboard_from_photos.py — extract storyboard images from each
scene's Photos/<scene>.zip and upload to Storyboard/.

For every scene that has a populated Photos/ folder but an empty
Storyboard/, this picks N evenly-spaced JPGs out of the photo zip and
re-uploads them under Storyboard/. The zip is read via S3 byte-range
requests — only the central directory + the picked entries are pulled,
not the whole multi-hundred-MB archive.

Filename convention preserves whatever the zip uses (typical:
``Performer1-Performer2-Photos_NNN.jpg``). Sorted then evenly sampled.

    python3 backfill_storyboard_from_photos.py                 # dry run
    python3 backfill_storyboard_from_photos.py --apply         # do it
    python3 backfill_storyboard_from_photos.py --scenes VRH0411,FPVR0152
    python3 backfill_storyboard_from_photos.py --apply --picks 30
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import re
import sqlite3
import sys
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

from botocore.exceptions import ClientError

import s4_client


_log = logging.getLogger("storyboard-backfill")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)


# Mac-side default — the same place sync_engine reads from on Windows.
_DEFAULT_DB_CANDIDATES: list[Path] = [
    Path.home() / "Scripts" / "eclatech_hub.db",
    Path(__file__).resolve().parent / "eclatech_hub.db",
]


def _find_db(explicit: str | None) -> Path:
    """Pick a SQLite DB to read scene asset flags from.

    The Mac side doesn't normally hold the hub DB — the canonical copy
    lives on Windows. So this is mostly used by callers passing
    ``--db`` explicitly to a SCP'd copy, or running on Windows.
    """
    if explicit:
        return Path(explicit)
    for c in _DEFAULT_DB_CANDIDATES:
        if c.exists():
            return c
    raise SystemExit(
        "No DB found. Pass --db /path/to/eclatech_hub.db (e.g. SCP'd from Windows)."
    )


# ── Streaming S3 reader ───────────────────────────────────────────────────────

class _S3RangeReader(io.RawIOBase):
    """Seekable file-like that reads an S3 object via Range requests.

    ``zipfile.ZipFile`` only needs ``read``, ``seek``, ``tell`` — keep
    the surface minimal. Each ``read`` issues one ``GetObject`` with
    ``Range: bytes=start-end``; an in-memory cache around the central
    directory keeps repeated reads cheap when ZipFile probes for the
    EOCD record.
    """

    def __init__(self, bucket: str, key: str, size: int) -> None:
        self._bucket = bucket
        self._key = key
        self._size = size
        self._pos = 0
        self._cache: bytes | None = None
        self._cache_start = 0
        self._cache_end = 0
        self._client = s4_client._client()

    # io.RawIOBase plumbing
    def readable(self) -> bool: return True
    def seekable(self) -> bool: return True

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self._pos = offset
        elif whence == io.SEEK_CUR:
            self._pos += offset
        elif whence == io.SEEK_END:
            self._pos = self._size + offset
        else:
            raise ValueError(f"bad whence: {whence}")
        if self._pos < 0:
            self._pos = 0
        return self._pos

    def read(self, size: int = -1) -> bytes:
        if self._pos >= self._size:
            return b""
        if size is None or size < 0:
            size = self._size - self._pos
        end = min(self._pos + size, self._size)

        # Serve from cache if we previously fetched this region.
        if self._cache and self._cache_start <= self._pos and end <= self._cache_end:
            slice_start = self._pos - self._cache_start
            slice_end = end - self._cache_start
            data = self._cache[slice_start:slice_end]
            self._pos = end
            return data

        # Otherwise issue a Range GET. Pad to 64KiB so adjacent zipfile
        # probes (EOCD, central directory header) don't each round-trip.
        block = max(end - self._pos, 65536)
        block_start = self._pos
        block_end = min(block_start + block, self._size) - 1
        resp = self._client.get_object(
            Bucket=self._bucket,
            Key=self._key,
            Range=f"bytes={block_start}-{block_end}",
        )
        body = resp["Body"].read()
        self._cache = body
        self._cache_start = block_start
        self._cache_end = block_start + len(body)
        # Now serve the originally-requested slice.
        slice_end = end - block_start
        data = body[:slice_end]
        self._pos = end
        return data


# ── Per-scene work ────────────────────────────────────────────────────────────

def _list_scene_objects(studio: str, scene_id: str) -> list[dict]:
    return [o for o in s4_client.list_objects(studio, prefix=f"{scene_id}/")]


def _largest_photos_zip(objects: list[dict]) -> dict | None:
    """Pick the largest .zip under Photos/.

    Some scenes hold a master archive next to a smaller one (e.g.
    ``_FPVR0001.zip`` 8K master alongside ``FPVR0001.zip`` 4K) — always
    prefer the biggest so we get the highest-resolution source for
    storyboard frames.
    """
    candidates = [
        o for o in objects
        if "/Photos/" in o["key"] and o["key"].lower().endswith(".zip")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda o: o["size"])


def _existing_storyboard_files(objects: list[dict]) -> list[str]:
    """Existing Storyboard/ image keys (jpg/jpeg/png), in S4 order."""
    return [
        o["key"] for o in objects
        if "/Storyboard/" in o["key"]
        and not o["key"].endswith("/")
        and o["key"].lower().endswith((".jpg", ".jpeg", ".png"))
    ]


def _evenly_spaced(items: list, n: int) -> list:
    """Pick n evenly-spaced entries from a sorted list (always includes
    the first and last)."""
    if len(items) <= n:
        return list(items)
    if n == 1:
        return [items[0]]
    return [items[int(i * (len(items) - 1) / (n - 1))] for i in range(n)]


def _pick_storyboard_entries(
    zf: zipfile.ZipFile, picks: int,
) -> list[zipfile.ZipInfo]:
    """Pick N JPG entries from the zip, preferring the 'Raw' subset
    matching real photoset conventions."""
    all_jpgs = [
        info for info in zf.infolist()
        if not info.is_dir()
        and info.filename.lower().endswith((".jpg", ".jpeg"))
        and not os.path.basename(info.filename).startswith(".")
    ]
    if not all_jpgs:
        return []

    # Same priority order comp_photoset uses: Raw/Scene Photos > anything-not-Storyboard > anything.
    def _score(name: str) -> int:
        nl = name.lower()
        if "raw" in nl and "scene" in nl: return 0
        if "storyboard" in nl:            return 2  # avoid recursive feedback if zip already had storyboard
        return 1

    by_score: dict[int, list[zipfile.ZipInfo]] = {}
    for info in all_jpgs:
        by_score.setdefault(_score(info.filename), []).append(info)

    chosen = next((by_score[s] for s in (0, 1, 2) if s in by_score), [])
    chosen.sort(key=lambda i: i.filename)
    return _evenly_spaced(chosen, picks)


def _process_scene(
    studio: str,
    scene_id: str,
    picks: int,
    apply: bool,
) -> tuple[str, str]:
    """Return (status, detail) — status ∈ {'ok', 'skip-has-story', 'skip-no-zip', 'error'}.

    Idempotency: a scene is "complete enough" if it already has at least
    ceil(picks * 0.8) JPGs in Storyboard/. Below that threshold the
    existing files are wiped and the scene is re-processed from the
    photos zip — handles partial uploads from a failed prior run.
    """
    try:
        bucket = s4_client._studio_to_bucket(studio)
        objs = _list_scene_objects(studio, scene_id)
    except Exception as exc:
        return ("error", f"list failed: {exc}")

    existing = _existing_storyboard_files(objs)
    threshold = max(1, (picks * 4 + 4) // 5)  # ceil(picks * 0.8)
    if len(existing) >= threshold:
        return ("skip-has-story", f"{len(existing)} ≥ {threshold}")

    if existing and apply:
        # Wipe partial uploads so we don't end up with mixed naming or
        # double-counted frames.
        client = s4_client._client()
        for k in existing:
            try:
                client.delete_object(Bucket=bucket, Key=k)
            except Exception as exc:  # noqa: BLE001
                _log.warning("[%s] delete %s failed: %s", scene_id, k, exc)
    zip_obj = _largest_photos_zip(objs)
    if zip_obj is None:
        return ("skip-no-zip", "no Photos/*.zip")
    # Log the chosen zip so dry-run output is auditable.
    _log.debug(
        "[%s] using %s (%.1f MB)",
        scene_id, zip_obj["key"], zip_obj["size"] / 1_048_576,
    )

    reader = _S3RangeReader(bucket, zip_obj["key"], zip_obj["size"])
    try:
        with zipfile.ZipFile(reader) as zf:
            entries = _pick_storyboard_entries(zf, picks)
            if not entries:
                return ("skip-no-zip", "no images inside zip")

            # Streamed extract + upload. Use a direct put_object (single
            # PUT) instead of boto3 upload_file — MEGA S4 has a multipart
            # quirk where retries surface InvalidPart/NoSuchUpload errors.
            # Storyboard JPGs are 1–10 MB, well under S3's 5 GB single-PUT
            # cap, so multipart is unnecessary anyway.
            import time
            uploaded: list[str] = []
            client = s4_client._client()
            for info in entries:
                base = os.path.basename(info.filename)
                out_key = f"{scene_id}/Storyboard/{base}"
                if not apply:
                    uploaded.append(out_key)
                    continue
                with zf.open(info) as src:
                    body = src.read()
                last_err: Exception | None = None
                for attempt in range(3):
                    try:
                        client.put_object(
                            Bucket=bucket,
                            Key=out_key,
                            Body=body,
                            ContentType="image/jpeg",
                        )
                        last_err = None
                        break
                    except Exception as exc:
                        last_err = exc
                        time.sleep(2 ** attempt)
                if last_err:
                    return ("error", f"put_object {out_key}: {last_err}")
                uploaded.append(out_key)

        return ("ok", f"{len(uploaded)} files")
    except (zipfile.BadZipFile, ClientError) as exc:
        return ("error", f"{type(exc).__name__}: {exc}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _scenes_needing_backfill(db_path: Path, only: set[str] | None) -> list[tuple[str, str]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, studio FROM scenes "
        "WHERE has_photos=1 AND has_storyboard=0 ORDER BY id"
    ).fetchall()
    conn.close()
    candidates = [(r["id"], r["studio"]) for r in rows]
    if only is not None:
        candidates = [c for c in candidates if c[0] in only]
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually upload (default: dry run)")
    parser.add_argument("--scenes",
                        help="Comma-separated scene IDs to limit the run to")
    parser.add_argument("--picks", type=int, default=20,
                        help="Storyboard images per scene (default 20)")
    parser.add_argument("--workers", type=int, default=3,
                        help="Concurrent scenes (default 3)")
    parser.add_argument("--db",
                        help="Path to eclatech_hub.db (default: ~/Scripts/eclatech_hub.db)")
    parser.add_argument("--limit", type=int,
                        help="Process at most N scenes (useful for testing)")
    args = parser.parse_args()

    only = (
        {s.strip() for s in args.scenes.split(",") if s.strip()}
        if args.scenes else None
    )
    db_path = _find_db(args.db)
    _log.info("Using DB: %s", db_path)

    targets = _scenes_needing_backfill(db_path, only)
    if args.limit:
        targets = targets[:args.limit]
    if not targets:
        _log.info("No scenes need backfill.")
        return 0
    _log.info("%d scene(s) targeted", len(targets))

    if not args.apply:
        _log.warning("DRY RUN — re-run with --apply to upload")

    counts: dict[str, int] = {"ok": 0, "skip-has-story": 0, "skip-no-zip": 0, "error": 0}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_process_scene, studio, sid, args.picks, args.apply): sid
            for sid, studio in targets
        }
        for i, fut in enumerate(as_completed(futures), 1):
            sid = futures[fut]
            try:
                status, detail = fut.result()
            except Exception as exc:
                status, detail = "error", str(exc)
            counts[status] = counts.get(status, 0) + 1
            tag = {
                "ok": "OK   ",
                "skip-has-story": "SKIP ",
                "skip-no-zip": "SKIP ",
                "error": "ERR  ",
            }.get(status, "?    ")
            _log.info("[%4d/%-4d] %s %-9s  %s  %s", i, len(targets), tag, sid, status, detail)

    _log.info("---")
    _log.info("Summary: %s", " ".join(f"{k}={v}" for k, v in counts.items()))
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
