"""test_uploads_e2e.py — exercise the full multipart upload flow against real
MEGA S4 the same way the browser does, but from Python.

Asserts the architecture works end-to-end:
  1. create_multipart_upload returns an UploadId
  2. presign_part returns a usable PUT URL
  3. PUT to that URL succeeds and returns an ETag header
  4. complete_multipart_upload assembles the parts into a real object
  5. head_object confirms the size matches what we sent
  6. cleanup deletes the test object

Run:  python3 test_uploads_e2e.py [--studio vrh] [--key e2e-test/...]
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time

import requests

import s4_client


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--studio", default="VRH")
    p.add_argument("--key", default=f"E2E0001/Description/uploads-e2e-{int(time.time())}.txt")
    p.add_argument("--size", type=int, default=12 * 1024 * 1024,
                   help="Bytes (default 12MB so we exercise multipart).")
    p.add_argument("--keep", action="store_true", help="Skip cleanup.")
    args = p.parse_args()

    studio = args.studio
    key = args.key
    print(f"Bucket: {s4_client.STUDIO_BUCKETS[s4_client._STUDIO_ALIASES.get(studio, studio).upper()]}  Key: {key}  Size: {args.size}")

    # ── Step 1: init ─────────────────────────────────────────────────────────
    print("\n[1] create_multipart_upload")
    upload_id = s4_client.create_multipart_upload(studio, key, content_type="text/plain")
    print(f"    upload_id = {upload_id}")

    # ── Step 2: split into parts ─────────────────────────────────────────────
    part_size = s4_client.PART_SIZE
    # Single-part if size <= part_size; otherwise floor(size/part_size) parts
    # of part_size + a final remainder. S3 requires every part except the last
    # to be ≥ 5 MB, so for a 12 MB test we'll use 2 parts of 8 MB + 4 MB —
    # below the configured PART_SIZE of 64 MB, but the S3 minimum is honored.
    test_part_size = max(5 * 1024 * 1024, args.size // 2 + 1) if args.size > 5 * 1024 * 1024 else args.size
    parts: list[dict] = []
    offset = 0
    part_number = 1
    while offset < args.size:
        end = min(offset + test_part_size, args.size)
        body = b"x" * (end - offset)
        print(f"\n[2.{part_number}] presign_part #{part_number} ({end - offset} bytes)")
        url = s4_client.presign_part(studio, key, upload_id, part_number)
        print(f"    url[:80] = {url[:80]}…")
        print(f"    PUT to S4")
        r = requests.put(url, data=body, headers={"Content-Type": "application/octet-stream"})
        if r.status_code not in (200, 204):
            print(f"    FAIL: HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
            try: s4_client.abort_multipart_upload(studio, key, upload_id)
            except Exception: pass
            return 2
        # The browser reads ETag from the response header — confirm it's there.
        etag = r.headers.get("ETag") or r.headers.get("etag") or ""
        if not etag:
            print(f"    FAIL: no ETag in response. Headers: {dict(r.headers)}", file=sys.stderr)
            try: s4_client.abort_multipart_upload(studio, key, upload_id)
            except Exception: pass
            return 3
        # Confirm the CORS expose-headers list includes ETag (matters for the
        # browser path — if MEGA stops exposing it, the browser path breaks).
        expose = r.headers.get("Access-Control-Expose-Headers", "")
        if "etag" not in expose.lower():
            print(f"    WARN: Access-Control-Expose-Headers does not list ETag: {expose!r}")
        print(f"    OK  ETag={etag}")
        parts.append({"PartNumber": part_number, "ETag": etag.strip('"')})
        offset = end
        part_number += 1

    # ── Step 3: complete ─────────────────────────────────────────────────────
    print(f"\n[3] complete_multipart_upload ({len(parts)} parts)")
    resp = s4_client.complete_multipart_upload(studio, key, upload_id, parts)
    final_etag = resp.get("ETag", "").strip('"')
    print(f"    OK  final_etag={final_etag}")

    # ── Step 4: verify ───────────────────────────────────────────────────────
    print(f"\n[4] head_object")
    head = s4_client.head_object(studio, key)
    if head is None:
        print("    FAIL: object not found after complete", file=sys.stderr)
        return 4
    print(f"    OK  size={head['size']}  content_type={head['content_type']}")
    assert head["size"] == args.size, f"size mismatch: head={head['size']} sent={args.size}"

    # ── Step 5: cleanup ──────────────────────────────────────────────────────
    if args.keep:
        print(f"\n[5] (skipping cleanup; --keep set)")
    else:
        print(f"\n[5] delete_object")
        s4_client.delete_object(studio, key)
        print(f"    OK")

    print("\n✅ end-to-end pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
