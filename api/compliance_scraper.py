"""Background scraper: MEGA `{SCENE_ID}/Legal/` folders → compliance_legal_files index.

Runs on the Windows API host (where boto3 + the SQLite DB live), invoked
either by a Windows Task Scheduler job (nightly) or on-demand via the
companion CLI script ``scrape_mega_legal.py``.

What it does:
  1. Walks every studio bucket via boto3 paginated list_objects_v2.
  2. Filters keys to `/Legal/` paths whose filename looks like real
     paperwork (PDF or ID-photo formats; no BTS .mp4, desktop.ini, ".DS_Store",
     "Copy of …" cruft, default-camera DSC_/IMG_ names).
  3. Classifies each file by filename heuristics (agreement / w9 / 2257 /
     id_photo / verification_photo / generic).
  4. Upserts into ``compliance_legal_files`` keyed by (studio, key).
  5. Drops rows whose key no longer exists on the bucket (so the index
     stays consistent if files are deleted/renamed).
  6. Updates ``compliance_legal_scan_meta`` with timing + counts.

Why not run inline in the API:
  - Bucket walks take 30–60 s on first cold scan; cached or not, doing
    this in the request path leads to client timeouts (we hit this in
    PR #214 with the 30 s default fetch cap).
  - The bulk importer needs the same normalized list — building it once
    in the DB and querying from both consumers is cheaper than re-walking.

Side effect-free outside the DB. No network writes (the scraper only
READS from MEGA). Talent name + doc-kind heuristics mirror the ones in
hub/app/(app)/compliance/compliance-database.tsx so the UI sees the same
classification whether the row came from the index or the live scan.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from api.database import get_db

_log = logging.getLogger(__name__)

# Studios we scan — canonical 4-letter codes that s4_client knows.
DEFAULT_STUDIOS: tuple[str, ...] = ("fpvr", "vrh", "vra", "njoi")


# ─── Filename heuristics (mirrored from compliance.py + the UI) ──────────────


_PAPERWORK_EXTS = (".pdf", ".jpg", ".jpeg", ".png", ".heic", ".webp")

_PAPERWORK_NAME_DENY = (
    "desktop.ini", "thumbs.db", ".ds_store", "icon\r",
)
_PAPERWORK_NAME_DENY_PREFIXES = (
    "copy of ",
    "dsc_", "dsc-",
    "img_", "img-",
    "photo ",
    "._",
)


def _is_paperwork_filename(filename: str) -> bool:
    low = filename.lower().strip()
    if not low or low in _PAPERWORK_NAME_DENY:
        return False
    if any(low.startswith(p) for p in _PAPERWORK_NAME_DENY_PREFIXES):
        return False
    if not any(low.endswith(ext) for ext in _PAPERWORK_EXTS):
        return False
    return True


# Talent name extraction. Three observed conventions:
#   1. CamelCase from the prepare flow:  JadaSnow-061220.pdf
#   2. Two-word lowercase + month name:  mike mancini oct 5 2019.pdf
#   3. Two-word + 6-digit date:          Marilyn Johnson 121822.pdf

_RE_CAMEL_HEAD = re.compile(r"^[A-Z][a-z]+([A-Z][a-z]+)+$")
_NON_NAMES = {
    "SignedAgreement", "SignedRelease", "ReleaseOriginal", "ModelRelease",
    "Disclosure", "Performer", "Custom", "Original", "Document", "Photo",
}
_RE_STOP = re.compile(r"\b(\d|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", re.I)
_RE_REJECT_NAME = re.compile(
    r"^(Signed|Agreement|Release|Disclosure|W ?9|2257|Mike Manicini|Custom Field|Test File)$",
    re.I,
)


def _guess_talent(filename: str) -> str:
    """Best-effort talent name extraction. Returns '' when no match."""
    stem = filename.rsplit(".", 1)[0]
    head = re.split(r"[-_ ]", stem, 1)[0]
    if _RE_CAMEL_HEAD.fullmatch(head) and head not in _NON_NAMES:
        return re.sub(r"([a-z])([A-Z])", r"\1 \2", head)

    m = _RE_STOP.search(stem)
    lead = stem[:m.start()].strip() if m else stem.strip()
    words = [w for w in re.split(r"[\s_\-]+", lead) if re.fullmatch(r"[a-zA-Z'.]+", w)]
    if len(words) < 2 or len(words[0]) < 2:
        return ""
    name = " ".join(w[0].upper() + w[1:].lower() for w in words[:2])
    if _RE_REJECT_NAME.match(name):
        return ""
    return name


_DOC_KIND_PATTERNS = [
    ("2257_disclosure",   re.compile(r"(2257|disclosure)", re.I)),
    ("w9",                re.compile(r"w-?9", re.I)),
    ("agreement",         re.compile(r"(agreement|release|contract)", re.I)),
    ("verification_photo", re.compile(r"(bunny.?ear)", re.I)),
    ("id_photo",          re.compile(r"(front|back|id|license|passport)", re.I)),
]


def _classify(filename: str) -> str:
    low = filename.lower()
    for kind, pat in _DOC_KIND_PATTERNS:
        if pat.search(low):
            return kind
    if low.endswith(".pdf"):
        return "pdf"
    if any(low.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".heic", ".webp")):
        return "photo"
    return "file"


# ─── Scanner ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class IndexedFile:
    studio: str           # canonical 4-letter UPPERCASE code (FPVR/VRH/VRA/NJOI)
    scene_id: str
    key: str
    filename: str
    size: int
    last_modified: str
    guessed_talent: str
    doc_kind: str


def _normalize_lm(lm) -> str:
    if lm is None:
        return ""
    try:
        return lm.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return str(lm)


def iter_legal_files(studios: Iterable[str] = DEFAULT_STUDIOS) -> Iterable[IndexedFile]:
    """Yield every paperwork-looking file in `/Legal/` across the given studios.

    Filters cruft before yield. Caller decides what to do with each one
    (typically: upsert into compliance_legal_files).
    """
    import s4_client  # type: ignore[import-not-found]

    for studio in studios:
        studio_upper = studio.upper()
        try:
            for obj in s4_client.list_objects(studio):
                key = obj["key"]
                low = key.lower()
                if "/legal/" not in low or key.endswith("/"):
                    continue
                filename = key.rsplit("/", 1)[-1]
                if not _is_paperwork_filename(filename):
                    continue
                head, _, _ = key.partition("/")
                try:
                    scene_id = s4_client.normalize_scene_id(head)
                except ValueError:
                    scene_id = head
                yield IndexedFile(
                    studio=studio_upper,
                    scene_id=scene_id,
                    key=key,
                    filename=filename,
                    size=int(obj.get("size") or 0),
                    last_modified=_normalize_lm(obj.get("last_modified")),
                    guessed_talent=_guess_talent(filename),
                    doc_kind=_classify(filename),
                )
        except Exception as exc:
            _log.warning("MEGA legal scan failed for %s: %s", studio, exc)


def run_scan(
    studios: Iterable[str] = DEFAULT_STUDIOS,
    *,
    progress_every: int = 500,
) -> dict:
    """Full reconciliation: replace the index with what's on the buckets.

    Returns a summary dict suitable for logging / showing in the admin UI.
    """
    studios = tuple(studios)
    started_at = time.time()
    seen_keys: set[tuple[str, str]] = set()  # (studio, key)
    upsert_sql = """
        INSERT INTO compliance_legal_files
            (studio, scene_id, key, filename, size, last_modified,
             guessed_talent, doc_kind, indexed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(studio, key) DO UPDATE SET
            scene_id        = excluded.scene_id,
            filename        = excluded.filename,
            size            = excluded.size,
            last_modified   = excluded.last_modified,
            guessed_talent  = excluded.guessed_talent,
            doc_kind        = excluded.doc_kind,
            indexed_at      = excluded.indexed_at;
    """

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%fZ")
    errors: list[str] = []
    total = 0

    with get_db() as conn:
        for f in iter_legal_files(studios):
            try:
                conn.execute(
                    upsert_sql,
                    (f.studio, f.scene_id, f.key, f.filename, f.size,
                     f.last_modified, f.guessed_talent, f.doc_kind, now_iso),
                )
                seen_keys.add((f.studio, f.key))
                total += 1
                if total % progress_every == 0:
                    conn.commit()
                    _log.info("scrape progress: %d files indexed", total)
            except Exception as exc:
                errors.append(f"{f.key}: {exc}")
        conn.commit()

        # Drop rows for keys that disappeared. Done per studio so a
        # mid-scan failure on one bucket doesn't nuke another's rows.
        deleted = 0
        for studio in studios:
            studio_upper = studio.upper()
            existing = conn.execute(
                "SELECT key FROM compliance_legal_files WHERE studio=?",
                (studio_upper,),
            ).fetchall()
            for row in existing:
                if (studio_upper, row["key"]) not in seen_keys:
                    conn.execute(
                        "DELETE FROM compliance_legal_files WHERE studio=? AND key=?",
                        (studio_upper, row["key"]),
                    )
                    deleted += 1

        duration_ms = int((time.time() - started_at) * 1000)
        conn.execute(
            """UPDATE compliance_legal_scan_meta
                  SET last_scan_at=?, last_scan_duration_ms=?, last_scan_files=?,
                      last_scan_studios=?, last_scan_errors=?
                WHERE id=1""",
            (
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                duration_ms,
                total,
                ",".join(s.upper() for s in studios),
                json.dumps(errors[:50]),
            ),
        )

    return {
        "studios": [s.upper() for s in studios],
        "files_indexed": total,
        "deleted_stale": deleted,
        "duration_ms": duration_ms,
        "error_count": len(errors),
        "errors_sample": errors[:5],
    }


def link_imported_signatures() -> int:
    """Best-effort link compliance_legal_files rows to their compliance_signatures
    counterparts via pdf_mega_path. Run after a bulk import so the UI can show
    "this file is already in records → click to edit" for MEGA rows.

    Returns number of rows updated.
    """
    sql = """
        UPDATE compliance_legal_files
           SET imported_signature_id = (
               SELECT cs.id
                 FROM compliance_signatures cs
                WHERE cs.pdf_mega_path LIKE '%' || compliance_legal_files.key
                  AND cs.scene_id = compliance_legal_files.scene_id
                LIMIT 1
           )
         WHERE imported_signature_id IS NULL
    """
    with get_db() as conn:
        cur = conn.execute(sql)
        n = cur.rowcount or 0
        conn.commit()
    return n
