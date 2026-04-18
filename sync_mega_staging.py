#!/usr/bin/env python3
"""
sync_mega_staging.py — Pull descriptions from Windows staging folder and upload to MEGA.

Runs on Mac. Pulls from Windows via SCP, uploads to MEGA via rclone,
then updates mega_scan.json and deploys it back to Windows.

Usage:
    python3 sync_mega_staging.py        # sync once
    python3 sync_mega_staging.py --watch # poll every 60s
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
WIN_HOST = "andre@100.90.90.68"
SSH_KEY = str(Path.home() / ".ssh" / "id_ed25519_win")
WIN_STAGING = "C:/Users/andre/eclatech-hub/mega_staging"
RCLONE_REMOTE = "mega_test"
MEGA_BASE = "Grail"
SCAN_FILE = Path.home() / "Library" / "CloudStorage" / "Dropbox" / "mega_scan.json"
WIN_SCAN = "C:/Users/andre/eclatech-hub/mega_scan.json"
LOCAL_TEMP = Path("/tmp/mega_staging_sync")

# MEGA blocks IPs on fast-paced requests. See rclone.org/mega/.
# --tpslimit paces API calls within a call; --retries recovers from rate-limit
# errors; time.sleep() between scenes spaces separate rclone invocations
# ~3s apart as the docs recommend.
_RETRY_FLAGS = [
    "--retries", "10",
    "--retries-sleep", "30s",
    "--low-level-retries", "10",
    "--tpslimit", "3",
    "--tpslimit-burst", "1",
]
_INTER_CALL_SLEEP = 3.0

STUDIO_MAP = {
    "VRH": "VRH",
    "FPVR": "FPVR",
    "VRA": "VRA",
    "NNJOI": "NNJOI",
}


def ssh_cmd(cmd: str, timeout: int = 30) -> str:
    result = subprocess.run(
        ["ssh", "-i", SSH_KEY, WIN_HOST, cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip()


def scp_from_win(remote_path: str, local_path: str):
    result = subprocess.run(
        ["scp", "-i", SSH_KEY, "-r", f"{WIN_HOST}:{remote_path}", local_path],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        print(f"  SCP error: {result.stderr.strip()}")


def scp_to_win(local_path: str, remote_path: str):
    subprocess.run(
        ["scp", "-i", SSH_KEY, local_path, f"{WIN_HOST}:{remote_path}"],
        capture_output=True, text=True, timeout=60
    )


def sync_once():
    """Pull staging, upload to MEGA, update scan, clean up."""
    # 1. Check if staging folder has any real files
    try:
        listing = ssh_cmd(f'powershell -Command "if (Test-Path \'{WIN_STAGING}\') {{ Get-ChildItem -Path \'{WIN_STAGING}\' -Recurse -File | Select-Object -ExpandProperty FullName }} else {{ }}"')
    except subprocess.TimeoutExpired:
        print("SSH timed out checking staging folder")
        return 0

    if not listing.strip():
        return 0

    files = [f for f in listing.splitlines() if f.strip() and (f.endswith('.docx') or f.endswith('.txt'))]
    if not files:
        return 0
    print(f"Found {len(files)} files in staging")

    # 2. Pull staging to local temp
    if LOCAL_TEMP.exists():
        subprocess.run(["rm", "-rf", str(LOCAL_TEMP)], capture_output=True)
    LOCAL_TEMP.mkdir(parents=True, exist_ok=True)
    scp_from_win(WIN_STAGING, str(LOCAL_TEMP))
    # SCP creates mega_staging/ subdir — adjust path if needed
    inner = LOCAL_TEMP / "mega_staging"
    staging_root = inner if inner.exists() else LOCAL_TEMP

    # 3. Upload each studio/scene to MEGA
    uploaded = []
    # Debug: show what was pulled
    pulled = list(LOCAL_TEMP.rglob("*"))
    print(f"  Pulled {len(pulled)} items to {LOCAL_TEMP}")
    for p in pulled[:10]:
        print(f"    {p.relative_to(LOCAL_TEMP)}")
    for studio_dir in staging_root.iterdir():
        if not studio_dir.is_dir():
            continue
        studio = studio_dir.name  # VRH, FPVR, etc.
        mega_studio = STUDIO_MAP.get(studio, studio)

        for scene_dir in studio_dir.iterdir():
            if not scene_dir.is_dir():
                continue
            scene_id_raw = scene_dir.name  # VRH758 or VRH0758
            # Zero-pad: VRH758 → VRH0758
            scene_id = re.sub(r'([A-Za-z]+)(\d+)', lambda m: m.group(1) + m.group(2).zfill(4), scene_id_raw)

            desc_dir = scene_dir / "Description"
            if not desc_dir.exists():
                continue

            desc_files = list(desc_dir.iterdir())
            if not desc_files:
                continue

            mega_scene_root = f"{MEGA_BASE}/{mega_studio}/{scene_id}"
            mega_path = f"{mega_scene_root}/Description/"

            # Create full folder structure if scene folder doesn't exist yet
            check = subprocess.run(
                ["rclone", "lsd", f"{RCLONE_REMOTE}:{mega_scene_root}", "--timeout", "30s", *_RETRY_FLAGS],
                capture_output=True, text=True, timeout=120
            )
            if check.returncode != 0 or not check.stdout.strip():
                print(f"  Creating folder structure for {scene_id}...")
                for subfolder in ["Description", "Legal", "Photos", "Storyboard", "Video Thumbnail", "Videos"]:
                    subprocess.run(
                        ["rclone", "mkdir", f"{RCLONE_REMOTE}:{mega_scene_root}/{subfolder}",
                         "--timeout", "30s", *_RETRY_FLAGS],
                        capture_output=True, text=True, timeout=120
                    )
                    time.sleep(_INTER_CALL_SLEEP)

            print(f"  Uploading {scene_id} → {RCLONE_REMOTE}:{mega_path}")

            result = subprocess.run(
                ["rclone", "copy", str(desc_dir), f"{RCLONE_REMOTE}:{mega_path}",
                 "--timeout", "120s", *_RETRY_FLAGS],
                capture_output=True, text=True, timeout=300
            )

            if result.returncode == 0:
                uploaded.append((scene_id, scene_id_raw, studio))
                print(f"    ✓ {scene_id}")
            else:
                print(f"    ✗ {scene_id}: {result.stderr.strip()}")

            time.sleep(_INTER_CALL_SLEEP)

    # 4. Update mega_scan.json
    if uploaded and SCAN_FILE.exists():
        with open(SCAN_FILE) as f:
            scan = json.load(f)
        uploaded_ids = {u[0] for u in uploaded}
        for s in scan.get("scenes", []):
            if s["scene_id"] in uploaded_ids:
                s["has_description"] = True
        with open(SCAN_FILE, "w") as f:
            json.dump(scan, f, ensure_ascii=False, indent=2)
        # Deploy updated scan to Windows
        scp_to_win(str(SCAN_FILE), WIN_SCAN)
        print(f"  Updated scan for {len(uploaded)} scenes")

    # 5. Clean up staging on Windows
    if uploaded:
        try:
            ssh_cmd(f"powershell -Command \"Remove-Item -Path '{WIN_STAGING}' -Recurse -Force -ErrorAction SilentlyContinue\"", timeout=15)
        except Exception:
            pass

    # 6. Clean up local temp
    subprocess.run(["rm", "-rf", str(LOCAL_TEMP)], capture_output=True)

    return len(uploaded)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="Poll every 60s")
    args = parser.parse_args()

    if args.watch:
        print("Watching staging folder... (Ctrl+C to stop)")
        while True:
            n = sync_once()
            if n:
                print(f"Synced {n} scenes to MEGA")
            time.sleep(60)
    else:
        n = sync_once()
        if n:
            print(f"Done. Synced {n} scenes to MEGA.")
        else:
            print("Nothing to sync.")


if __name__ == "__main__":
    main()
