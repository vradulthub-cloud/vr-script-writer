#!/usr/bin/env python3
"""
sync_mega_staging.py — Pull descriptions from Windows staging folder, upload to MEGA S4.

Runs on Mac. Pulls staging from Windows via SCP, uploads each scene's
Description/ contents to its studio's S4 bucket via s4_client, updates
mega_scan.json so the hub immediately reflects has_description=True, and
deploys the scan back to Windows.

Replaces the legacy rclone-based path that targeted mega_test:/Grail/{STUDIO}/...
in MEGA cloud. With S4, bucket == studio, key starts at the scene id, no
/Grail/ prefix.

Usage:
    python3 sync_mega_staging.py        # sync once
    python3 sync_mega_staging.py --watch # poll every 60s
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Load S4 creds (cron-friendly).
ENV_FILE = Path.home() / ".config" / "eclatech" / "s4.env"
if ENV_FILE.exists():
    for _line in ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v)

import s4_client  # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────
WIN_HOST = "andre@100.90.90.68"
SSH_KEY = str(Path.home() / ".ssh" / "id_ed25519_win")
WIN_STAGING = "C:/Users/andre/eclatech-hub/mega_staging"
SCAN_FILE = Path.home() / "Library" / "CloudStorage" / "Dropbox" / "mega_scan.json"
WIN_SCAN = "C:/Users/andre/eclatech-hub/mega_scan.json"
LOCAL_TEMP = Path("/tmp/mega_staging_sync")

# Staging folder uses studio names that aren't always the canonical S4 codes
# (e.g. Streamlit-era code wrote NNJOI). s4_client handles the alias.
def studio_to_canonical(staging_studio: str) -> str:
    """Normalize whatever the staging folder names a studio to the canonical
    code that s4_client uses."""
    canon = s4_client._STUDIO_ALIASES.get(staging_studio, staging_studio).upper()
    if canon in s4_client.STUDIO_BUCKETS:
        return canon
    raise ValueError(f"Unknown studio in staging path: {staging_studio!r}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def ssh_cmd(cmd: str, timeout: int = 30) -> str:
    result = subprocess.run(
        ["ssh", "-i", SSH_KEY, WIN_HOST, cmd],
        capture_output=True, text=True, timeout=timeout,
    )
    return result.stdout.strip()


def scp_from_win(remote_path: str, local_path: str) -> None:
    result = subprocess.run(
        ["scp", "-i", SSH_KEY, "-r", f"{WIN_HOST}:{remote_path}", local_path],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        print(f"  SCP error: {result.stderr.strip()}")


def scp_to_win(local_path: str, remote_path: str) -> None:
    subprocess.run(
        ["scp", "-i", SSH_KEY, local_path, f"{WIN_HOST}:{remote_path}"],
        capture_output=True, text=True, timeout=60,
    )


# ── Core ──────────────────────────────────────────────────────────────────────

def sync_once() -> int:
    """Pull staging, upload to S4, update scan, clean up. Returns # uploaded."""
    # 1. Check if staging folder has any real files.
    try:
        listing = ssh_cmd(
            "powershell -Command "
            f"\"if (Test-Path '{WIN_STAGING}') {{ "
            "Get-ChildItem -Path '" + WIN_STAGING + "' -Recurse -File | "
            "Select-Object -ExpandProperty FullName }} else {{ }}\""
        )
    except subprocess.TimeoutExpired:
        print("SSH timed out checking staging folder")
        return 0

    if not listing.strip():
        return 0

    files = [f for f in listing.splitlines()
             if f.strip() and (f.endswith(".docx") or f.endswith(".txt"))]
    if not files:
        return 0
    print(f"Found {len(files)} files in staging")

    # 2. Pull staging to local temp.
    if LOCAL_TEMP.exists():
        subprocess.run(["rm", "-rf", str(LOCAL_TEMP)], capture_output=True)
    LOCAL_TEMP.mkdir(parents=True, exist_ok=True)
    scp_from_win(WIN_STAGING, str(LOCAL_TEMP))
    inner = LOCAL_TEMP / "mega_staging"
    staging_root = inner if inner.exists() else LOCAL_TEMP

    # 3. Upload each scene's description files to S4.
    uploaded: list[tuple[str, str, str]] = []  # (scene_id, scene_id_raw, studio)
    pulled = list(LOCAL_TEMP.rglob("*"))
    print(f"  Pulled {len(pulled)} items to {LOCAL_TEMP}")
    for p in pulled[:10]:
        print(f"    {p.relative_to(LOCAL_TEMP)}")

    for studio_dir in staging_root.iterdir():
        if not studio_dir.is_dir():
            continue
        try:
            studio = studio_to_canonical(studio_dir.name)
        except ValueError as exc:
            print(f"  [WARN] {exc}; skipping {studio_dir}")
            continue

        for scene_dir in studio_dir.iterdir():
            if not scene_dir.is_dir():
                continue
            scene_id_raw = scene_dir.name  # VRH758 or VRH0758
            # Zero-pad / canonicalize.
            try:
                scene_id = s4_client.normalize_scene_id(scene_id_raw)
            except ValueError:
                # Fall back to the existing zero-pad regex for whatever the
                # staging folder produced.
                scene_id = re.sub(
                    r"([A-Za-z]+)(\d+)",
                    lambda m: m.group(1).upper() + m.group(2).zfill(4),
                    scene_id_raw,
                )

            desc_dir = scene_dir / "Description"
            if not desc_dir.exists():
                continue

            desc_files = [f for f in desc_dir.iterdir() if f.is_file()]
            if not desc_files:
                continue

            print(f"  Uploading {scene_id} ({len(desc_files)} files) → {s4_client.STUDIO_BUCKETS[studio]}/{scene_id}/Description/")

            ok = True
            for f in desc_files:
                key = s4_client.key_for(scene_id, "Description", f.name)
                content_type = (
                    "text/plain" if f.suffix.lower() == ".txt" else
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    if f.suffix.lower() == ".docx" else None
                )
                try:
                    s4_client.put_object(studio, key, f, content_type=content_type)
                    print(f"    ✓ {key}")
                except Exception as exc:
                    print(f"    ✗ {key}: {exc}")
                    ok = False
            if ok:
                uploaded.append((scene_id, scene_id_raw, studio))

    # 4. Update mega_scan.json.
    if uploaded and SCAN_FILE.exists():
        with open(SCAN_FILE) as f:
            scan = json.load(f)
        uploaded_ids = {u[0] for u in uploaded}
        for s in scan.get("scenes", []):
            if s["scene_id"] in uploaded_ids:
                s["has_description"] = True
        with open(SCAN_FILE, "w") as f:
            json.dump(scan, f, ensure_ascii=False, indent=2)
        scp_to_win(str(SCAN_FILE), WIN_SCAN)
        print(f"  Updated scan for {len(uploaded)} scenes")

    # 5. Clean up Windows staging.
    if uploaded:
        try:
            ssh_cmd(
                "powershell -Command "
                f"\"Remove-Item -Path '{WIN_STAGING}' -Recurse -Force -ErrorAction SilentlyContinue\"",
                timeout=15,
            )
        except Exception:
            pass

    # 6. Clean up local temp.
    subprocess.run(["rm", "-rf", str(LOCAL_TEMP)], capture_output=True)

    return len(uploaded)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="Poll every 60s")
    args = parser.parse_args()

    if args.watch:
        print("Watching staging folder… (Ctrl+C to stop)")
        while True:
            n = sync_once()
            if n:
                print(f"Synced {n} scenes to MEGA S4")
            time.sleep(60)
    else:
        n = sync_once()
        if n:
            print(f"Done. Synced {n} scenes to MEGA S4.")
        else:
            print("Nothing to sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
