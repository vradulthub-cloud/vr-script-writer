#!/usr/bin/env python3
"""migrate_drive_to_s4.py — Stream files from a shared Google Drive folder into a MEGA S4 bucket.

Use case: you've migrated most of a studio's content to MEGA S4 but still
have leftovers in Google Drive. This script walks the Drive folder, mirrors
the directory layout into the studio's S4 bucket, and skips anything that
already exists with a matching size (idempotent across reruns / resumes).

Auth: uses the existing service_account.json. The Drive folder must be
shared (Viewer or above) with that service account's email:

    $ python3 -c "import json; print(json.load(open('service_account.json'))['client_email'])"
    roster-updater@model-roster-updater.iam.gserviceaccount.com

Usage:
    python3 migrate_drive_to_s4.py \\
        --drive-folder 1mcFj5nQp5AkboW3PvKMgQ0ArOe0ToBxp \\
        --studio VRH \\
        --dest-prefix ""                # mirrors Drive structure into bucket root

    python3 migrate_drive_to_s4.py \\
        --drive-folder 1mcFj5nQp5AkboW3PvKMgQ0ArOe0ToBxp \\
        --studio VRH \\
        --dest-prefix VRH0042/Photos    # rooted under one scene's subfolder

    --dry-run          enumerate without uploading
    --max-bytes N      stop after N bytes uploaded (smoke-test guard)
    --skip-existing    skip if dest exists with matching size (default ON)
    --no-skip-existing always re-upload, overwriting

Streams each file via a SpooledTemporaryFile (memory under 50 MB, then disk)
straight into s4_client.put_object — no full-folder pre-download.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

# Load S4 creds.
ENV_FILE = Path.home() / ".config" / "eclatech" / "s4.env"
if ENV_FILE.exists():
    for _line in ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v)

import s4_client  # noqa: E402

from google.oauth2.service_account import Credentials  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402
from googleapiclient.http import MediaIoBaseDownload  # noqa: E402
from googleapiclient.errors import HttpError  # noqa: E402

SERVICE_ACCOUNT_FILE = Path("/Users/andrewninn/Scripts/service_account.json")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Files Drive considers "Google Docs" formats can't be downloaded raw — must
# be exported. We don't expect these in a Grail VRH backup, but skip cleanly
# if encountered.
GOOGLE_NATIVE_TYPES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/vnd.google-apps.form",
    "application/vnd.google-apps.drawing",
}


def drive_client():
    creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT_FILE), scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def walk_folder(svc, folder_id: str, parent_path: str = ""):
    """Yield {id, name, mimeType, size, path} for every non-folder descendant.

    `path` is the relative path from the root folder (e.g. "Photos/foo.jpg").
    """
    page_token = None
    while True:
        resp = svc.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType, size)",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        for f in resp.get("files", []) or []:
            child_path = f"{parent_path}/{f['name']}" if parent_path else f["name"]
            if f["mimeType"] == "application/vnd.google-apps.folder":
                yield from walk_folder(svc, f["id"], child_path)
            else:
                yield {
                    "id":       f["id"],
                    "name":     f["name"],
                    "mimeType": f["mimeType"],
                    "size":     int(f.get("size") or 0),
                    "path":     child_path,
                }
        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def needs_upload(studio: str, key: str, src_size: int, skip_existing: bool) -> bool:
    if not skip_existing:
        return True
    head = s4_client.head_object(studio, key)
    if head is None:
        return True
    return head["size"] != src_size


def stream_to_s4(svc, file_id: str, studio: str, key: str, total_size: int) -> int:
    """Download from Drive into a temp file, then upload to S4.

    Returns the byte count actually transferred (== total_size on success).
    """
    request = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
    with tempfile.SpooledTemporaryFile(max_size=50 * 1024 * 1024) as buf:
        downloader = MediaIoBaseDownload(buf, request, chunksize=16 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        buf.seek(0)
        # Spill to a real file so boto3 upload_file can stream it.
        with tempfile.NamedTemporaryFile(delete=False) as on_disk:
            try:
                while True:
                    chunk = buf.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    on_disk.write(chunk)
                on_disk.flush()
                on_disk.close()
                s4_client.put_object(studio, key, on_disk.name)
            finally:
                try:
                    os.unlink(on_disk.name)
                except OSError:
                    pass
    return total_size


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mirror a Google Drive folder into a MEGA S4 studio bucket."
    )
    parser.add_argument("--drive-folder", required=True,
                        help="Drive folder ID (the 1mcFj... part of the share URL)")
    parser.add_argument("--studio", required=True, choices=list(s4_client.STUDIO_BUCKETS),
                        help="Target studio bucket")
    parser.add_argument("--dest-prefix", default="",
                        help="Prefix to prepend to every key in the destination bucket "
                             "(default: empty — mirrors Drive layout at bucket root)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Enumerate without uploading")
    parser.add_argument("--max-bytes", type=int, default=0,
                        help="Stop after N bytes uploaded (default: unlimited)")
    parser.add_argument("--skip-existing", dest="skip_existing", action="store_true", default=True)
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    args = parser.parse_args()

    bucket = s4_client.STUDIO_BUCKETS[args.studio]
    prefix = args.dest_prefix.rstrip("/")
    print(f"Source: drive folder {args.drive_folder}")
    print(f"Dest:   s3://{bucket}/{prefix + '/' if prefix else ''}")
    print(f"Mode:   {'DRY RUN' if args.dry_run else 'UPLOAD'}; skip_existing={args.skip_existing}")
    print()

    svc = drive_client()
    try:
        files = list(walk_folder(svc, args.drive_folder))
    except HttpError as exc:
        print(f"ERR: Drive walk failed: {exc}", file=sys.stderr)
        if exc.resp.status == 404:
            print(f"     Did you share the folder with the service account?\n"
                  f"     {Credentials.from_service_account_file(str(SERVICE_ACCOUNT_FILE), scopes=SCOPES).service_account_email}",
                  file=sys.stderr)
        return 2

    total_count = len(files)
    total_bytes = sum(f["size"] for f in files)
    print(f"Found {total_count} files, {total_bytes / 1e9:.2f} GB total.\n")

    if args.dry_run:
        for f in files[:30]:
            print(f"  {f['size']:12,d}  {f['path']}")
        if total_count > 30:
            print(f"  ... and {total_count - 30} more")
        print("\n(dry run — re-run without --dry-run to upload)")
        return 0

    uploaded_bytes = 0
    n_uploaded = 0
    n_skipped = 0
    n_native = 0
    n_failed = 0

    started = time.time()
    for i, f in enumerate(files, 1):
        key = f"{prefix}/{f['path']}" if prefix else f["path"]
        # MEGA S4 keys cannot start with '/'.
        key = key.lstrip("/")

        if f["mimeType"] in GOOGLE_NATIVE_TYPES:
            print(f"  [{i}/{total_count}] SKIP (Google native): {f['path']}")
            n_native += 1
            continue
        if not needs_upload(args.studio, key, f["size"], args.skip_existing):
            print(f"  [{i}/{total_count}] EXISTS: {key}")
            n_skipped += 1
            continue
        if args.max_bytes and uploaded_bytes + f["size"] > args.max_bytes:
            print(f"  --max-bytes hit ({uploaded_bytes:,} uploaded); stopping.")
            break
        try:
            print(f"  [{i}/{total_count}] {f['size']:>12,} B  {key}", flush=True)
            stream_to_s4(svc, f["id"], args.studio, key, f["size"])
            uploaded_bytes += f["size"]
            n_uploaded += 1
        except (HttpError, OSError) as exc:
            print(f"    FAILED: {exc}", file=sys.stderr)
            n_failed += 1

    elapsed = time.time() - started
    print()
    print(f"Done in {elapsed:.0f}s.")
    print(f"  uploaded: {n_uploaded} files, {uploaded_bytes / 1e9:.2f} GB")
    print(f"  existed:  {n_skipped} files (skipped)")
    print(f"  google-native skipped: {n_native}")
    print(f"  failed: {n_failed}")
    return 0 if n_failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
