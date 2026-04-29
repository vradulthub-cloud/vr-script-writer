"""s4_client.py — MEGA S4 (S3-compatible) client for the Eclatech Hub.

Single source of truth for every S4 operation. boto3 under the hood. One
bucket per studio (fpvr/vrh/vra/njoi). Object keys start at the scene ID — no
``/Grail/`` and no studio prefix. Example: in bucket ``vrh`` the
description for scene VRH0762 lives at ``VRH0762/Description/VRH0762_description.docx``.

Required environment variables (loaded once on first call):

    S4_ENDPOINT_URL       default https://s3.g.s4.mega.io
    S4_ACCESS_KEY_ID
    S4_SECRET_ACCESS_KEY
    S4_REGION             default us-east-1

Smoke test:

    python3 s4_client.py probe
"""

from __future__ import annotations

import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Iterator

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


# ── Studio map ────────────────────────────────────────────────────────────────

STUDIO_BUCKETS: dict[str, str] = {
    "FPVR": "fpvr",
    "VRH":  "vrh",
    "VRA":  "vra",
    "NJOI": "njoi",
}

# Codebase uses a few different identifiers for each studio (see CLAUDE.md
# Studio Name Mapping). Resolve them all to canonical 4-letter codes.
_STUDIO_ALIASES: dict[str, str] = {
    "NNJOI":      "NJOI",
    "FuckPassVR": "FPVR",
    "FuckpassVR": "FPVR",
    "VRHush":     "VRH",
    "VRAllure":   "VRA",
    "NaughtyJOI": "NJOI",
    "fpvr":       "FPVR",
    "vrh":        "VRH",
    "vra":        "VRA",
    "njoi":       "NJOI",
}


def _studio_to_bucket(studio: str) -> str:
    canon = _STUDIO_ALIASES.get(studio, studio).upper()
    if canon not in STUDIO_BUCKETS:
        raise ValueError(
            f"Unknown studio {studio!r}; expected one of {list(STUDIO_BUCKETS)} "
            f"or an alias in {sorted(_STUDIO_ALIASES)}"
        )
    return STUDIO_BUCKETS[canon]


# ── Scene ID normalization ────────────────────────────────────────────────────

_SCENE_ID_RE = re.compile(r"^([A-Za-z]+)0*(\d+)$")


def normalize_scene_id(raw: str) -> str:
    """Uppercase prefix + 4-digit zero-padded number.

        "vrh0002"  -> "VRH0002"
        "FPVR12"   -> "FPVR0012"
        "NJOI0145" -> "NJOI0145"

    The S4 buckets contain a mix of casing (the migration preserved whatever
    was there). Normalize on read so the rest of the codebase only sees the
    canonical form already used in the DB.
    """
    m = _SCENE_ID_RE.match(raw.strip())
    if not m:
        raise ValueError(f"Not a scene ID: {raw!r}")
    return f"{m.group(1).upper()}{int(m.group(2)):04d}"


def key_for(scene_id: str, *parts: str) -> str:
    """Build an S3 key. Scene ID is normalized; remaining parts joined as-is.

        key_for("VRH0762", "Description", "x.docx")
            -> "VRH0762/Description/x.docx"

    Pass case-sensitive subfolder names exactly: "Description", "Videos",
    "Photos", "Storyboard", "Legal", "Video Thumbnail".
    """
    sid = normalize_scene_id(scene_id)
    return f"{sid}/" if not parts else "/".join((sid, *parts))


# ── boto3 client ──────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _client():
    endpoint = os.environ.get("S4_ENDPOINT_URL", "https://s3.g.s4.mega.io")
    access   = os.environ.get("S4_ACCESS_KEY_ID")
    secret   = os.environ.get("S4_SECRET_ACCESS_KEY")
    region   = os.environ.get("S4_REGION", "us-east-1")
    if not access or not secret:
        raise RuntimeError(
            "S4 credentials missing. Set S4_ACCESS_KEY_ID and "
            "S4_SECRET_ACCESS_KEY in the environment."
        )
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name=region,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
        ),
    )


def reset_client() -> None:
    """Drop the cached boto3 client. Call after rotating env vars in tests."""
    _client.cache_clear()


# ── Operations ────────────────────────────────────────────────────────────────

def list_objects(studio: str, prefix: str = "") -> Iterator[dict]:
    """Yield every object under ``prefix`` in the studio's bucket.

    Each dict: ``{key, size, last_modified, etag}``. Pages internally — safe
    for buckets with thousands of objects.
    """
    bucket = _studio_to_bucket(studio)
    paginator = _client().get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []) or []:
            yield {
                "key":           obj["Key"],
                "size":          obj["Size"],
                "last_modified": obj["LastModified"],
                "etag":          obj.get("ETag", "").strip('"'),
            }


def head_object(studio: str, key: str) -> dict | None:
    """Object metadata, or None if it doesn't exist."""
    bucket = _studio_to_bucket(studio)
    try:
        resp = _client().head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return None
        raise
    return {
        "size":          resp["ContentLength"],
        "last_modified": resp["LastModified"],
        "content_type":  resp.get("ContentType", ""),
        "etag":          resp.get("ETag", "").strip('"'),
    }


def resolve_key(studio: str, key: str) -> str | None:
    """Resolve the canonical key to its actual on-disk casing.

    The migration left 23 VRH scenes with lowercase prefixes (`vrh0500/...`)
    alongside the 281 uppercase ones. Code holding a canonical key calls
    this to find the real one. Returns None if neither casing exists.

    Costs at most 2 HEAD requests; cache results in callers that do many
    lookups for the same scene.
    """
    if head_object(studio, key) is not None:
        return key
    head, sep, rest = key.partition("/")
    if not sep:
        return None
    lower_key = f"{head.lower()}/{rest}"
    if lower_key != key and head_object(studio, lower_key) is not None:
        return lower_key
    return None


def get_object(studio: str, key: str, dest_path: str | Path) -> Path:
    """Download to ``dest_path`` (parents created). Returns the path."""
    bucket = _studio_to_bucket(studio)
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _client().download_file(bucket, key, str(dest))
    return dest


def put_object(studio: str, key: str, src_path: str | Path,
               content_type: str | None = None) -> None:
    bucket = _studio_to_bucket(studio)
    extra: dict[str, str] = {}
    if content_type:
        extra["ContentType"] = content_type
    _client().upload_file(str(src_path), bucket, key, ExtraArgs=extra or None)


def delete_object(studio: str, key: str) -> None:
    bucket = _studio_to_bucket(studio)
    _client().delete_object(Bucket=bucket, Key=key)


PRESIGN_DEFAULT_TTL = 7 * 24 * 60 * 60  # 7 days — the SigV4 maximum.


def presign(studio: str, key: str, ttl: int = PRESIGN_DEFAULT_TTL) -> str:
    """Presigned GET URL. SigV4 caps TTL at 7 days; for compilation links use
    the weekly ``refresh_comp_links.py`` cron."""
    bucket = _studio_to_bucket(studio)
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=ttl,
    )


# ── Probe CLI ─────────────────────────────────────────────────────────────────

def _probe() -> int:
    print(f"Endpoint: {os.environ.get('S4_ENDPOINT_URL', 'https://s3.g.s4.mega.io')}")
    print(f"Region:   {os.environ.get('S4_REGION', 'us-east-1')}")
    failures = 0
    for studio, bucket in STUDIO_BUCKETS.items():
        try:
            resp = _client().list_objects_v2(Bucket=bucket, MaxKeys=1)
            objs = resp.get("Contents", []) or []
            sample = objs[0]["Key"] if objs else "(empty)"
            count_hint = "1+" if resp.get("IsTruncated") or objs else "0"
            print(f"  OK  {studio:5s} ({bucket}): {count_hint:3s}  sample={sample}")
        except Exception as exc:
            print(f"  ERR {studio:5s} ({bucket}): {exc}")
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "probe":
        sys.exit(_probe())
    print(f"usage: {sys.argv[0]} probe", file=sys.stderr)
    sys.exit(2)
