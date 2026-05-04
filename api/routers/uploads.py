"""
Uploads API router — drag-and-drop upload dashboard backend.

The hub's /uploads page lets users drop files (≤ ~3 GB each) and the system
auto-routes them to the right scene + subfolder in MEGA S4. Files travel
**directly from the browser to S4** via presigned multipart-upload URLs;
this router just brokers the part URLs and finalizes the assembled object.

Routes (all require an authenticated hub user; no role gate):
  POST /api/uploads/multipart/init         — start multipart, return UploadId + part plan
  POST /api/uploads/multipart/sign-parts   — return presigned PUT URLs for the requested parts
  POST /api/uploads/multipart/complete     — finalize, write audit log, flip scene flags
  POST /api/uploads/multipart/abort        — cancel multipart + clean lingering
  GET  /api/uploads/head                   — idempotency probe (uses resolve_key)
  GET  /api/uploads/history                — recent uploads (newest first)

3 GB worst case at 64 MB parts = 48 parts. Browser PUTs 4 in flight, captures
ETag from each, and posts the {part_number, etag} list to /complete.
"""
from __future__ import annotations

import io
import logging
import math
import os
import re
import threading
import zipfile
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.auth import CurrentUser
from api.database import get_db
from api import uploads_log
from api import notification_dispatcher
import s4_client

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/uploads", tags=["uploads"])


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PART_SIZE = s4_client.PART_SIZE                # 64 MB
MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024         # 5 GB hard ceiling (we expect ≤ 3 GB)
MAX_PARTS = 10_000                             # S3 multipart spec maximum

# Subfolder → scene-table flag bumps. Keep in sync with mega_scan.py.
_SUBFOLDER_FLAGS: dict[str, dict[str, str]] = {
    "Description":     {"flag": "has_description"},
    "Videos":          {"flag": "has_videos",     "counter": "video_count"},
    "Photos":          {"flag": "has_photos"},
    "Storyboard":      {"flag": "has_storyboard", "counter": "storyboard_count"},
    "Video Thumbnail": {"flag": "has_thumbnail"},
    "Legal":           {},  # no scene flag tracked
}

# Legal subfolder names (case-sensitive) — refuse anything else so we don't end
# up with rogue keys like "videos/" or "Final/".
_VALID_SUBFOLDERS = set(_SUBFOLDER_FLAGS.keys())


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class InitRequest(BaseModel):
    studio: str = Field(..., description="Canonical or alias studio name (FPVR/VRH/VRA/NJOI or any alias).")
    scene_id: str = Field(..., description="Scene ID, normalized server-side.")
    subfolder: str = Field(..., description="One of Description/Videos/Photos/Storyboard/Video Thumbnail/Legal.")
    filename: str = Field(..., description="Final filename within the subfolder.")
    size: int = Field(..., gt=0, le=MAX_FILE_SIZE)
    content_type: Optional[str] = None


class InitResponse(BaseModel):
    upload_id: str
    bucket: str
    key: str
    part_size: int
    part_count: int


class SignPartsRequest(BaseModel):
    studio: str
    key: str
    upload_id: str
    part_numbers: list[int]


class PartUrl(BaseModel):
    part_number: int
    url: str


class SignPartsResponse(BaseModel):
    urls: list[PartUrl]


class PartTag(BaseModel):
    part_number: int = Field(..., ge=1, le=MAX_PARTS)
    etag: str


class CompleteRequest(BaseModel):
    studio: str
    key: str
    upload_id: str
    parts: list[PartTag]
    size: int
    subfolder: str


class CompleteResponse(BaseModel):
    ok: bool
    bucket: str
    key: str
    etag: str
    presigned_url: str


class VerifyRequest(BaseModel):
    studio: str
    key: str
    upload_id: str


class AbortRequest(BaseModel):
    studio: str
    key: str
    upload_id: str


class HeadResponse(BaseModel):
    exists: bool
    size: Optional[int] = None
    etag: Optional[str] = None
    canonical_key: Optional[str] = None  # Lowercase fallback for legacy VRH


class HistoryRow(BaseModel):
    ts: float
    user_email: str = ""
    user_name: str = ""
    studio: str
    scene_id: str
    subfolder: str
    filename: str
    key: str
    size: int = 0
    mode: str = "direct"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._\- ]+$")


def _resolve_studio(studio: str) -> str:
    """Map any of the alias spellings to canonical (FPVR/VRH/VRA/NJOI). Raises
    400 if unknown, so callers don't have to catch ValueError themselves."""
    canon = s4_client._STUDIO_ALIASES.get(studio, studio).upper()
    if canon not in s4_client.STUDIO_BUCKETS:
        raise HTTPException(status_code=400, detail=f"Unknown studio: {studio!r}")
    return canon


def _normalize_scene_id(raw: str) -> str:
    try:
        return s4_client.normalize_scene_id(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _validate_subfolder(subfolder: str) -> str:
    if subfolder not in _VALID_SUBFOLDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid subfolder {subfolder!r}; allowed: {sorted(_VALID_SUBFOLDERS)}",
        )
    return subfolder


def _validate_filename(filename: str) -> str:
    name = filename.strip()
    if not name or not _SAFE_FILENAME_RE.match(name):
        raise HTTPException(
            status_code=400,
            detail="Filename must contain only letters, digits, spaces, dot, underscore, hyphen.",
        )
    if name.startswith(".") or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return name


def _build_key(scene_id: str, subfolder: str, filename: str) -> str:
    return s4_client.key_for(scene_id, subfolder, filename)


def _bump_scene_flag(scene_id: str, subfolder: str) -> None:
    """Flip the relevant ``has_<asset>=True`` (and bump counter where one
    exists) on the ``scenes`` row so the Missing tab updates without waiting
    for the nightly ``scan_mega.py`` cron. Best-effort — log and swallow on
    error since the audit log is the source of truth."""
    spec = _SUBFOLDER_FLAGS.get(subfolder, {})
    flag = spec.get("flag")
    counter = spec.get("counter")
    if not flag:
        return
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT id FROM scenes WHERE id = ?", (scene_id,),
            ).fetchone()
            if not row:
                # Scene doesn't exist in the table yet — sync_scenes will
                # pick it up on the next pass.
                return
            if counter:
                conn.execute(
                    f"UPDATE scenes SET {flag} = 1, {counter} = {counter} + 1 WHERE id = ?",
                    (scene_id,),
                )
            else:
                conn.execute(
                    f"UPDATE scenes SET {flag} = 1 WHERE id = ?", (scene_id,),
                )
            conn.commit()
    except Exception:
        _log.exception("bump_scene_flag failed (scene=%s flag=%s)", scene_id, flag)


# ---------------------------------------------------------------------------
# ZIP → Storyboard extraction (background, after Photos upload)
# ---------------------------------------------------------------------------

class _S3RangeReader(io.RawIOBase):
    """Seekable file-like backed by S3 Range GET requests.

    Only the central directory + selected entries are fetched — not the
    full archive. Borrowed from backfill_storyboard_from_photos.py."""

    def __init__(self, bucket: str, key: str, size: int) -> None:
        self._bucket = bucket
        self._key = key
        self._size = size
        self._pos = 0
        self._cache: bytes | None = None
        self._cache_start = 0
        self._cache_end = 0
        self._client = s4_client._client()

    def readable(self) -> bool: return True
    def seekable(self) -> bool: return True
    def tell(self) -> int: return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self._pos = offset
        elif whence == io.SEEK_CUR:
            self._pos += offset
        elif whence == io.SEEK_END:
            self._pos = self._size + offset
        self._pos = max(self._pos, 0)
        return self._pos

    def read(self, size: int = -1) -> bytes:
        if self._pos >= self._size:
            return b""
        if size is None or size < 0:
            size = self._size - self._pos
        end = min(self._pos + size, self._size)
        if self._cache and self._cache_start <= self._pos and end <= self._cache_end:
            data = self._cache[self._pos - self._cache_start : end - self._cache_start]
            self._pos = end
            return data
        block = max(end - self._pos, 65536)
        block_start = self._pos
        block_end = min(block_start + block, self._size) - 1
        resp = self._client.get_object(
            Bucket=self._bucket, Key=self._key,
            Range=f"bytes={block_start}-{block_end}",
        )
        body = resp["Body"].read()
        self._cache = body
        self._cache_start = block_start
        self._cache_end = block_start + len(body)
        data = body[: end - block_start]
        self._pos = end
        return data


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _extract_web_storyboard(studio: str, scene_id: str, zip_key: str) -> None:
    """Read a Photos ZIP from S4 via range requests, pull every image inside
    the Web/ folder, and upload each one to {scene_id}/Storyboard/."""
    bucket = s4_client.STUDIO_BUCKETS[studio]
    head = s4_client.head_object(studio, zip_key)
    if not head:
        _log.warning("storyboard-extract: ZIP not found key=%s", zip_key)
        return
    size = head["size"]

    reader = _S3RangeReader(bucket, zip_key, size)
    try:
        zf = zipfile.ZipFile(reader)
    except zipfile.BadZipFile:
        _log.warning("storyboard-extract: bad zip key=%s", zip_key)
        return

    def _is_web_storyboard(name: str) -> bool:
        parts = [p.lower() for p in name.replace("\\", "/").split("/")]
        for i in range(len(parts) - 1):
            if parts[i] == "web" and parts[i + 1] == "storyboard":
                return True
        return False

    web_images = [
        info for info in zf.infolist()
        if not info.is_dir()
        and os.path.splitext(info.filename)[1].lower() in _IMAGE_EXTS
        and _is_web_storyboard(info.filename)
    ]

    if not web_images:
        _log.info("storyboard-extract: no Web/Storyboard/ images in %s", zip_key)
        return

    client = s4_client._client()
    uploaded = 0
    for info in web_images:
        basename = os.path.basename(info.filename)
        if not basename or basename.startswith("."):
            continue
        dest_key = f"{scene_id}/Storyboard/{basename}"
        try:
            data = zf.read(info)
            client.put_object(
                Bucket=bucket, Key=dest_key, Body=data,
                ContentType="image/jpeg",
            )
            uploaded += 1
        except Exception:
            _log.exception("storyboard-extract: failed to upload %s", dest_key)

    if uploaded:
        _bump_scene_flag(scene_id, "Storyboard")
        _log.info(
            "storyboard-extract: %d images from Web/ → %s/Storyboard/",
            uploaded, scene_id,
        )


def _maybe_extract_storyboard_bg(
    studio: str, scene_id: str, subfolder: str, key: str,
) -> None:
    """If the completed upload is a ZIP in Photos/, fire off background
    extraction of the Web/ folder → Storyboard/."""
    if subfolder != "Photos" or not key.lower().endswith(".zip"):
        return
    def _run():
        try:
            _extract_web_storyboard(studio, scene_id, key)
        except Exception:
            _log.exception("storyboard-extract background failed key=%s", key)
    threading.Thread(target=_run, daemon=True).start()


# Subfolder → notification event type. Anything not listed (e.g. Video
# Thumbnail) doesn't fire a notification on its own.
_SUBFOLDER_EVENT_TYPES: dict[str, str] = {
    "Photos":      "photos_uploaded",
    "Videos":      "video_uploaded",
    "Description": "description_uploaded",
    "Storyboard":  "storyboard_uploaded",
    "Legal":       "legal_uploaded",
}


def _dispatch_upload_event(
    user: dict, studio: str, scene_id: str, subfolder: str, filename: str,
) -> None:
    """Fan a completed upload out via the notification dispatcher. Best-
    effort — never raises, since the upload already succeeded."""
    event_type = _SUBFOLDER_EVENT_TYPES.get(subfolder)
    if not event_type:
        return
    label = subfolder.lower()
    actor = user.get("name") or user.get("email") or "someone"
    title = f"{subfolder} uploaded — {scene_id}"
    message = f"{actor} uploaded {filename} to {scene_id}/{subfolder} ({studio})."
    link = f"/missing?scene={scene_id}"
    try:
        notification_dispatcher.dispatch(
            notification_dispatcher.NotificationEvent(
                event_type=event_type,
                title=title,
                message=message,
                link=link,
            ),
        )
    except Exception:
        _log.exception("dispatch %s failed scene=%s", event_type, scene_id)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/multipart/init", response_model=InitResponse)
async def multipart_init(req: InitRequest, user: CurrentUser):
    studio = _resolve_studio(req.studio)
    scene_id = _normalize_scene_id(req.scene_id)
    subfolder = _validate_subfolder(req.subfolder)
    filename = _validate_filename(req.filename)
    key = _build_key(scene_id, subfolder, filename)

    part_count = max(1, math.ceil(req.size / PART_SIZE))
    if part_count > MAX_PARTS:
        raise HTTPException(status_code=400, detail="File too large (would exceed 10000 parts)")

    try:
        upload_id = s4_client.create_multipart_upload(
            studio, key, content_type=req.content_type,
        )
    except Exception as exc:
        _log.exception("multipart init failed (key=%s)", key)
        raise HTTPException(status_code=502, detail=f"S4 init failed: {exc}")

    _log.info(
        "multipart init user=%s key=%s size=%s parts=%s upload_id=%s",
        user.get("name"), key, req.size, part_count, upload_id,
    )
    return InitResponse(
        upload_id=upload_id,
        bucket=s4_client.STUDIO_BUCKETS[studio],
        key=key,
        part_size=PART_SIZE,
        part_count=part_count,
    )


@router.post("/multipart/sign-parts", response_model=SignPartsResponse)
async def multipart_sign_parts(req: SignPartsRequest, user: CurrentUser):
    studio = _resolve_studio(req.studio)
    if not req.part_numbers:
        raise HTTPException(status_code=400, detail="part_numbers must not be empty")
    if any(p < 1 or p > MAX_PARTS for p in req.part_numbers):
        raise HTTPException(status_code=400, detail="part numbers must be 1..10000")

    urls: list[PartUrl] = []
    for n in req.part_numbers:
        try:
            url = s4_client.presign_part(studio, req.key, req.upload_id, n)
        except Exception as exc:
            _log.exception("presign_part failed key=%s part=%s", req.key, n)
            raise HTTPException(status_code=502, detail=f"presign failed: {exc}")
        urls.append(PartUrl(part_number=n, url=url))
    return SignPartsResponse(urls=urls)


@router.post("/multipart/complete", response_model=CompleteResponse)
async def multipart_complete(req: CompleteRequest, user: CurrentUser):
    studio = _resolve_studio(req.studio)
    subfolder = _validate_subfolder(req.subfolder)
    if not req.parts:
        raise HTTPException(status_code=400, detail="parts must not be empty")

    parts_sorted = sorted(req.parts, key=lambda p: p.part_number)
    parts_payload = [
        {"PartNumber": p.part_number, "ETag": p.etag} for p in parts_sorted
    ]

    try:
        resp = s4_client.complete_multipart_upload(
            studio, req.key, req.upload_id, parts_payload,
        )
    except Exception as exc:
        _log.exception("complete failed key=%s upload_id=%s", req.key, req.upload_id)
        # Try to release the lingering upload so storage doesn't leak.
        try:
            s4_client.abort_multipart_upload(studio, req.key, req.upload_id)
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=f"S4 complete failed: {exc}")

    final_etag = (resp.get("ETag") or "").strip('"')

    # Derive scene_id + filename from the key for the audit log + flag bump.
    parts_path = req.key.split("/", 2)
    scene_id = parts_path[0] if parts_path else ""
    filename = parts_path[2] if len(parts_path) > 2 else parts_path[-1]
    _bump_scene_flag(scene_id, subfolder)

    uploads_log.append({
        "user_email": user.get("email", ""),
        "user_name":  user.get("name", ""),
        "studio":     studio,
        "scene_id":   scene_id,
        "subfolder":  subfolder,
        "filename":   filename,
        "key":        req.key,
        "size":       req.size,
        "mode":       "direct",
        "etag":       final_etag,
    })

    presigned = ""
    try:
        presigned = s4_client.presign(studio, req.key)
    except Exception:
        _log.exception("presign post-complete failed (non-fatal) key=%s", req.key)

    _maybe_extract_storyboard_bg(studio, scene_id, subfolder, req.key)
    _dispatch_upload_event(user, studio, scene_id, subfolder, filename)
    _log.info("upload complete user=%s key=%s size=%s", user.get("name"), req.key, req.size)
    return CompleteResponse(
        ok=True,
        bucket=s4_client.STUDIO_BUCKETS[studio],
        key=req.key,
        etag=final_etag,
        presigned_url=presigned,
    )


@router.post("/multipart/verify")
async def multipart_verify(req: VerifyRequest, user: CurrentUser):
    """Check whether a multipart upload is still alive on S4.  The browser
    calls this before resuming a saved upload — if the UploadId has expired
    we return ``{alive: false}`` and the client starts a fresh upload instead
    of burning 4 retries per part against a dead ID."""
    studio = _resolve_studio(req.studio)
    alive = s4_client.is_multipart_alive(studio, req.key, req.upload_id)
    return {"alive": alive}


@router.post("/multipart/abort")
async def multipart_abort(req: AbortRequest, user: CurrentUser):
    studio = _resolve_studio(req.studio)
    try:
        s4_client.abort_multipart_upload(studio, req.key, req.upload_id)
    except Exception:
        # The specific upload_id may already be gone — fall through to the
        # broader cleanup that catches any orphaned multiparts on this key.
        _log.warning("abort_multipart_upload failed (continuing to broad clean)")
    aborted = s4_client.abort_lingering_multipart(studio, req.key)
    _log.info("upload aborted user=%s key=%s lingering=%s", user.get("name"), req.key, aborted)
    return {"ok": True, "aborted_lingering": aborted}


@router.get("/head", response_model=HeadResponse)
async def head(
    user: CurrentUser,
    studio: str = Query(...),
    key: str = Query(...),
):
    """Idempotency probe — does an object already exist at this (studio, key)?
    Uses ``resolve_key`` so the 23 lowercase VRH scene prefixes still match."""
    canon = _resolve_studio(studio)
    actual_key = s4_client.resolve_key(canon, key)
    if not actual_key:
        return HeadResponse(exists=False)
    head = s4_client.head_object(canon, actual_key) or {}
    return HeadResponse(
        exists=True,
        size=head.get("size"),
        etag=head.get("etag"),
        canonical_key=actual_key,
    )


@router.get("/history", response_model=list[HistoryRow])
async def history(user: CurrentUser, limit: int = Query(50, ge=1, le=500)):
    rows = uploads_log.read_recent(limit=limit)
    out: list[HistoryRow] = []
    for r in rows:
        try:
            out.append(HistoryRow(**{
                "ts":         float(r.get("ts") or 0),
                "user_email": r.get("user_email", ""),
                "user_name":  r.get("user_name", ""),
                "studio":     r.get("studio", ""),
                "scene_id":   r.get("scene_id", ""),
                "subfolder":  r.get("subfolder", ""),
                "filename":   r.get("filename", ""),
                "key":        r.get("key", ""),
                "size":       int(r.get("size") or 0),
                "mode":       r.get("mode", "direct"),
            }))
        except Exception:
            continue
    return out
