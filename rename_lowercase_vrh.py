#!/usr/bin/env python3
"""rename_lowercase_vrh.py — Backfill 23 lowercase VRH scene prefixes to uppercase.

The S4 vrh bucket has 281 uppercase scene prefixes (VRH0001/...) alongside 23
lowercase ones (vrh0002/...). The migration preserved whatever casing was on
disk. Code that holds canonical (always uppercase) scene IDs falls back via
s4_client.resolve_key() until this runs, then it's purely defensive.

Per-object cost: 1 HEAD (collision check) + 1 server-side COPY + 1 DELETE. No
local download/upload — entirely server-side, fast, and preserves checksums.

Usage:
    python3 rename_lowercase_vrh.py             # dry run (default)
    python3 rename_lowercase_vrh.py --execute   # perform the rename
    python3 rename_lowercase_vrh.py --studio FPVR --execute   # any studio

Safe to re-run; skips any scene that already has its uppercase variant on
disk (collision check), and silently no-ops if there are no lowercase prefixes.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

# Load S4 creds from the persistent env file.
ENV_FILE = Path.home() / ".config" / "eclatech" / "s4.env"
if ENV_FILE.exists():
    for _line in ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v)

import s4_client  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402


def find_lowercase_scenes(studio: str) -> dict[str, list[tuple[str, int]]]:
    """Walk the bucket; return {lowercase_prefix: [(key, size), ...]}."""
    by_prefix: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for obj in s4_client.list_objects(studio):
        head, sep, _ = obj["key"].partition("/")
        if not sep:
            continue
        # Only treat as lowercase if it differs from its uppercase form.
        if head != head.upper():
            by_prefix[head].append((obj["key"], obj["size"]))
    return by_prefix


def rename_scene(studio: str, lower_prefix: str,
                 files: list[tuple[str, int]], execute: bool) -> tuple[int, int]:
    """Copy each object to its uppercase key, delete the lowercase original.

    Returns (n_renamed, n_skipped). n_skipped counts collisions (uppercase
    already exists; we leave the lowercase alone for manual review).
    """
    bucket = s4_client._studio_to_bucket(studio)
    upper_prefix = lower_prefix.upper()
    client = s4_client._client()

    renamed = 0
    skipped = 0
    for old_key, size in files:
        new_key = upper_prefix + old_key[len(lower_prefix):]
        # Refuse to overwrite — if uppercase already exists, two casings
        # contained different files. Surface that for human review.
        try:
            client.head_object(Bucket=bucket, Key=new_key)
            print(f"    SKIP collision: {new_key} exists (would lose {old_key} @ {size:,}B)")
            skipped += 1
            continue
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in ("404", "NoSuchKey", "NotFound"):
                raise

        if execute:
            client.copy_object(
                Bucket=bucket,
                Key=new_key,
                CopySource={"Bucket": bucket, "Key": old_key},
                MetadataDirective="COPY",
            )
            client.delete_object(Bucket=bucket, Key=old_key)
        renamed += 1
    return renamed, skipped


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rename lowercase scene prefixes in an S4 studio bucket to uppercase."
    )
    parser.add_argument("--execute", action="store_true",
                        help="Actually perform the rename (default: dry run)")
    parser.add_argument("--studio", default="VRH", choices=list(s4_client.STUDIO_BUCKETS),
                        help="Studio bucket to clean up (default: VRH — the only one with known lowercase prefixes)")
    args = parser.parse_args()

    bucket = s4_client.STUDIO_BUCKETS[args.studio]
    print(f"Scanning {args.studio} bucket ({bucket}) for lowercase scene prefixes…", flush=True)

    lower = find_lowercase_scenes(args.studio)
    if not lower:
        print("No lowercase prefixes found. Nothing to do.")
        return 0

    n_scenes = len(lower)
    n_files = sum(len(v) for v in lower.values())
    n_bytes = sum(size for files in lower.values() for _, size in files)
    print(f"\nFound {n_scenes} lowercase scene(s), {n_files} objects, {n_bytes / 1e9:.2f} GB:")
    for prefix in sorted(lower):
        files = lower[prefix]
        size = sum(s for _, s in files)
        print(f"  {prefix} -> {prefix.upper()}  ({len(files)} objects, {size / 1e6:.1f} MB)")

    if not args.execute:
        print("\n(dry run — re-run with --execute to perform the rename)")
        return 0

    print(f"\nExecuting rename of {n_files} objects in bucket {bucket}…\n", flush=True)
    total_renamed = 0
    total_skipped = 0
    for prefix in sorted(lower):
        upper = prefix.upper()
        print(f"[{prefix} -> {upper}]")
        renamed, skipped = rename_scene(args.studio, prefix, lower[prefix], execute=True)
        total_renamed += renamed
        total_skipped += skipped
        print(f"  renamed {renamed}, skipped {skipped} of {len(lower[prefix])}")
    print(f"\nDone. {total_renamed} objects renamed, {total_skipped} skipped (collisions).")
    return 0 if total_skipped == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
