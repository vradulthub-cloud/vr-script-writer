#!/usr/bin/env python3
"""migrate_drive_to_s4_v2.py — Bulk-migrate scene folders from a Drive folder to S4.

Smarter than v1:
  - Discovers top-level scene folders first (493 in our VRH backup), shows ETA
  - Processes one scene at a time with per-scene progress
  - Concurrent file uploads within each scene (default 4 workers)
  - Idempotent: HEAD each S4 key; skip if size matches
  - Normalizes scene IDs to canonical uppercase (matches s4_client.normalize_scene_id)
  - Periodically prints elapsed/remaining

Usage:
    python3 migrate_drive_to_s4_v2.py --drive-folder <ID> --studio VRH
    python3 migrate_drive_to_s4_v2.py --drive-folder <ID> --studio VRH --dry-run
    python3 migrate_drive_to_s4_v2.py --drive-folder <ID> --studio VRH --only VRH0409 VRH0410
    python3 migrate_drive_to_s4_v2.py --drive-folder <ID> --studio VRH --workers 8
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

# Load creds
ENV_FILE = Path.home() / ".config" / "eclatech" / "s4.env"
if ENV_FILE.exists():
    for ln in ENV_FILE.read_text().splitlines():
        if "=" in ln and not ln.startswith("#"):
            k, v = ln.strip().split("=", 1); os.environ.setdefault(k, v)

sys.path.insert(0, "/Users/andrewninn/Scripts")
import s4_client  # noqa: E402

from google.oauth2.service_account import Credentials  # noqa: E402
from googleapiclient.discovery import build  # noqa: E402
from googleapiclient.http import MediaIoBaseDownload  # noqa: E402
from googleapiclient.errors import HttpError  # noqa: E402

SERVICE_ACCOUNT_FILE = "/Users/andrewninn/Scripts/service_account.json"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

GOOGLE_NATIVE_TYPES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/vnd.google-apps.form",
    "application/vnd.google-apps.drawing",
}

_print_lock = Lock()


def vprint(*args, **kwargs):
    kwargs.setdefault("flush", True)
    with _print_lock:
        print(*args, **kwargs)


_thread_local = threading.local()


def drive_client():
    """Thread-local Drive service. googleapiclient's underlying httplib2 isn't
    thread-safe, so each thread needs its own client + creds."""
    svc = getattr(_thread_local, "svc", None)
    if svc is not None:
        return svc
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    _thread_local.svc = svc
    return svc


def list_children(_unused_svc_arg, folder_id: str):
    svc = drive_client()
    """Return all children of a folder (paginated)."""
    out = []
    page = None
    while True:
        resp = svc.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType, size)",
            pageSize=1000,
            pageToken=page,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        out.extend(resp.get("files", []))
        page = resp.get("nextPageToken")
        if not page: break
    return out


def walk_scene(svc, scene_folder: dict, base_path: str = "") -> list[dict]:
    """Recursively list files under one scene folder.

    Returns [{id, name, size, path}] where path is relative to the scene folder
    (e.g. "Description/foo.docx"). Skips google-native types.
    """
    files: list[dict] = []
    children = list_children(svc, scene_folder["id"])
    for c in children:
        rel = f"{base_path}/{c['name']}" if base_path else c["name"]
        if c["mimeType"] == "application/vnd.google-apps.folder":
            files.extend(walk_scene(svc, c, rel))
        elif c["mimeType"] not in GOOGLE_NATIVE_TYPES:
            files.append({
                "id":   c["id"],
                "name": c["name"],
                "size": int(c.get("size") or 0),
                "path": rel,
            })
    return files


def stream_file(_svc, file_id: str, studio: str, key: str, dry_run: bool) -> int:
    """Download from Drive into temp file, upload to S4. Returns bytes uploaded."""
    if dry_run:
        return 0
    svc = drive_client()
    request = svc.files().get_media(fileId=file_id, supportsAllDrives=True)
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        try:
            downloader = MediaIoBaseDownload(tf, request, chunksize=16 * 1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            tf.flush()
            size = tf.tell()
            tf.close()
            s4_client.put_object(studio, key, tf.name)
            return size
        finally:
            try: os.unlink(tf.name)
            except OSError: pass


def process_scene(svc, scene_folder: dict, studio: str, dry_run: bool, workers: int) -> dict:
    """Walk + upload one scene. Returns stats dict."""
    raw_name = scene_folder["name"]
    try:
        canon = s4_client.normalize_scene_id(raw_name)
    except ValueError:
        return {"scene": raw_name, "skipped": True, "reason": "not-scene-shaped"}

    t0 = time.time()
    files = walk_scene(svc, scene_folder)
    if not files:
        return {"scene": canon, "uploaded": 0, "skipped": 0, "bytes": 0, "elapsed": time.time() - t0, "empty": True}

    # Decide which need uploading.
    plan: list[tuple[dict, str]] = []  # (file, s4_key)
    skip_count = 0
    for f in files:
        s4_key = f"{canon}/{f['path']}"
        head = s4_client.head_object(studio, s4_key)
        if head and head["size"] == f["size"]:
            skip_count += 1
            continue
        plan.append((f, s4_key))

    total_bytes = sum(f["size"] for f, _ in plan)
    if not plan:
        return {"scene": canon, "uploaded": 0, "skipped": skip_count, "bytes": 0,
                "elapsed": time.time() - t0, "all_present": True}

    if dry_run:
        return {"scene": canon, "uploaded": len(plan), "skipped": skip_count,
                "bytes": total_bytes, "elapsed": time.time() - t0, "dry": True}

    uploaded = 0
    failed = 0
    bytes_done = 0
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {
                pool.submit(stream_file, svc, f["id"], studio, key, False): (f, key)
                for f, key in plan
            }
            for fut in as_completed(futs):
                f, _ = futs[fut]
                try:
                    bytes_done += fut.result()
                    uploaded += 1
                except Exception as exc:
                    failed += 1
                    vprint(f"      ! {f['path']}: {exc}")
    else:
        for f, key in plan:
            try:
                bytes_done += stream_file(svc, f["id"], studio, key, False)
                uploaded += 1
            except Exception as exc:
                failed += 1
                vprint(f"      ! {f['path']}: {exc}")

    return {"scene": canon, "uploaded": uploaded, "skipped": skip_count,
            "bytes": bytes_done, "failed": failed, "elapsed": time.time() - t0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drive-folder", required=True)
    parser.add_argument("--studio", required=True, choices=list(s4_client.STUDIO_BUCKETS))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", nargs="+", default=None,
                        help="Only process these scene IDs (e.g. VRH0409 VRH0410)")
    parser.add_argument("--workers", type=int, default=4,
                        help="Concurrent uploads per scene (default 4)")
    parser.add_argument("--scene-workers", type=int, default=2,
                        help="Concurrent scenes (default 2)")
    args = parser.parse_args()

    bucket = s4_client.STUDIO_BUCKETS[args.studio]
    vprint(f"Drive folder: {args.drive_folder}")
    vprint(f"Dest bucket:  {bucket}")
    vprint(f"Mode:         {'DRY RUN' if args.dry_run else 'UPLOAD'}; workers={args.workers}, scene_workers={args.scene_workers}")
    vprint()

    svc = drive_client()
    vprint("Discovering scene folders…", end=" ", flush=True)
    top = list_children(svc, args.drive_folder)
    SCENE_RE = re.compile(rf"^{args.studio}\d+$", re.IGNORECASE)
    scene_folders = [f for f in top
                     if f["mimeType"] == "application/vnd.google-apps.folder"
                     and SCENE_RE.match(f["name"])]
    vprint(f"found {len(scene_folders)}.")

    if args.only:
        wanted = {s.upper() for s in args.only}
        scene_folders = [f for f in scene_folders
                         if s4_client.normalize_scene_id(f["name"]) in wanted]
        vprint(f"  filtered to {len(scene_folders)} matching --only")

    if not scene_folders:
        vprint("Nothing to migrate.")
        return 0

    started = time.time()
    total_uploaded = 0
    total_skipped = 0
    total_bytes = 0
    total_failed = 0

    # Process scenes in parallel
    with ThreadPoolExecutor(max_workers=args.scene_workers) as pool:
        futs = {
            pool.submit(process_scene, svc, sf, args.studio, args.dry_run, args.workers): sf
            for sf in scene_folders
        }
        n_done = 0
        for fut in as_completed(futs):
            sf = futs[fut]
            n_done += 1
            try:
                stats = fut.result()
            except Exception as exc:
                vprint(f"  [{n_done}/{len(scene_folders)}] {sf['name']}: ERR {exc}")
                continue
            if stats.get("skipped_reason") or stats.get("skipped") == True:
                continue
            up   = stats.get("uploaded", 0)
            sk   = stats.get("skipped", 0)
            mb   = stats.get("bytes", 0) / 1e6
            el   = stats.get("elapsed", 0)
            fail = stats.get("failed", 0)
            tag = "DRY" if stats.get("dry") else ("OK" if not fail else "PART")
            note = ""
            if stats.get("empty"):           note = " [empty]"
            elif stats.get("all_present"):   note = " [already in S4]"
            vprint(f"  [{n_done}/{len(scene_folders)}] {tag} {stats['scene']}: "
                   f"+{up} uploaded, {sk} skipped, {mb:.1f} MB, {el:.0f}s{note}"
                   + (f" ({fail} FAILED)" if fail else ""))
            total_uploaded += up
            total_skipped  += sk
            total_bytes    += stats.get("bytes", 0)
            total_failed   += fail

    elapsed = time.time() - started
    vprint()
    vprint(f"Done in {elapsed:.0f}s ({elapsed/60:.1f} min).")
    vprint(f"  uploaded: {total_uploaded} files, {total_bytes/1e9:.2f} GB")
    vprint(f"  already-existed: {total_skipped} files (skipped)")
    if total_failed:
        vprint(f"  FAILED: {total_failed} files (re-run to retry)")
    return 0 if not total_failed else 2


if __name__ == "__main__":
    sys.exit(main())
