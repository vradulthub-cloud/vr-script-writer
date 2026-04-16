#!/usr/bin/env python3
"""
scan_mega.py — Scan MEGA for scene folders missing Description .docx files.

Usage:
    python3 scan_mega.py          # scan folders modified in last 30 days
    python3 scan_mega.py --force  # scan ALL folders regardless of age
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

RCLONE_REMOTE = "mega_test"

STUDIOS = {
    "FPVR": "Grail/FPVR",
    "VRH":  "Grail/VRH",
    "VRA":  "Grail/VRA",
    "NJOI": "Grail/NNJOI",  # folder name NNJOI, but scene prefix is NJOI
}

DROPBOX_PATH = Path.home() / "Library" / "CloudStorage" / "Dropbox"
OUTPUT_FILE = DROPBOX_PATH / "mega_scan.json"

RECENT_DAYS = 30


# ── Helpers ───────────────────────────────────────────────────────────────────

def rclone_lsd(remote_path: str) -> list[str]:
    """Run `rclone lsd` and return stdout lines. Returns [] on error."""
    cmd = ["rclone", "lsd", f"{RCLONE_REMOTE}:{remote_path}", "--timeout", "600s"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=660)
        if result.returncode != 0:
            print(f"  [WARN] rclone lsd failed for {remote_path}: {result.stderr.strip()}", file=sys.stderr)
            return []
        return result.stdout.splitlines()
    except subprocess.TimeoutExpired:
        print(f"  [WARN] rclone lsd timed out for {remote_path}", file=sys.stderr)
        return []
    except FileNotFoundError:
        print("[ERROR] rclone not found in PATH", file=sys.stderr)
        sys.exit(1)


def rclone_ls(remote_path: str) -> list[str]:
    """Run `rclone ls` and return file paths. Returns [] on error."""
    cmd = ["rclone", "ls", f"{RCLONE_REMOTE}:{remote_path}", "--timeout", "600s"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=660)
        if result.returncode != 0:
            print(f"  [WARN] rclone ls failed for {remote_path}: {result.stderr.strip()}", file=sys.stderr)
            return []
        # Each line: "   12345 path/to/file.ext"
        paths = []
        for line in result.stdout.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                paths.append(parts[1])
        return paths
    except subprocess.TimeoutExpired:
        print(f"  [WARN] rclone ls timed out for {remote_path}", file=sys.stderr)
        return []


def parse_lsd_line(line: str):
    """
    Parse a line from `rclone lsd` output.
    Format: '          -1 2026-03-13 08:58:23        -1 FOLDER_NAME'
    Returns (folder_name, mtime_str) or None if unparseable.
    """
    parts = line.strip().split()
    # Expected: dummy(-1), date(YYYY-MM-DD), time(HH:MM:SS), dummy(-1), folder_name
    if len(parts) < 5:
        return None
    try:
        date_str = parts[1]   # e.g. 2026-03-13
        time_str = parts[2]   # e.g. 08:58:23
        folder_name = parts[4]
        mtime_str = f"{date_str} {time_str}"
        return folder_name, mtime_str
    except IndexError:
        return None


def camel_to_spaced(s: str) -> str:
    """'ClaraTrinity' → 'Clara Trinity'"""
    return re.sub(r'([A-Z])', r' \1', s).strip()


def extract_talents(file_paths: list[str]) -> tuple[str, str]:
    """
    Extract female/male talent names from filenames in any subfolder.
    Filenames use CamelCase names joined by hyphens:
      Videos/ClaraTrinity-DannySteele-180-POV-FPVR-2min_1k.mp4
      Storyboard/KitanaMontana-Nice-NJOI-Photos_001.jpg
      Photos/EmmaRosie-Solo-Photos.zip
    Priority: Videos > Storyboard > Photos > Legal (prefer video filenames).
    """
    # Sort by priority: Videos first, then Storyboard, Photos, Legal
    priority = {"Videos": 0, "Storyboard": 1, "Photos": 2, "Legal": 3}
    sorted_paths = sorted(file_paths, key=lambda p: priority.get(p.replace("\\", "/").split("/")[0], 99))

    for p in sorted_paths:
        p_norm = p.replace("\\", "/")
        folder = p_norm.split("/")[0] if "/" in p_norm else ""
        if folder not in ("Videos", "Storyboard", "Photos", "Legal"):
            continue
        basename = p_norm.split("/")[-1].rsplit(".", 1)[0]
        # Strip trailing _001 etc from storyboard files
        basename = re.sub(r'_\d+$', '', basename)
        parts = basename.split("-")
        names = []
        for part in parts:
            if re.match(r'^[A-Z][a-z]+[A-Z]', part):
                names.append(camel_to_spaced(part))
            else:
                break
        if names:
            female = names[0]
            male   = names[1] if len(names) > 1 else ""
            return female, male
    return "", ""


_DESC_EXTS = (".doc", ".docx", ".txt", ".rtf")


def has_description(file_paths: list[str]) -> bool:
    """Check if any file in a Description folder is a text/document type (.doc, .docx, .txt, .rtf)."""
    for p in file_paths:
        p_norm = p.replace("\\", "/")
        if ("Description/" in p_norm or p_norm.startswith("Description/")) and p_norm.lower().endswith(_DESC_EXTS):
            return True
    return False


def is_recent(mtime_str: str, days: int) -> bool:
    """Return True if mtime_str (YYYY-MM-DD HH:MM:SS) is within the last `days` days."""
    try:
        mtime = datetime.strptime(mtime_str, "%Y-%m-%d %H:%M:%S")
        cutoff = datetime.now() - timedelta(days=days)
        return mtime >= cutoff
    except ValueError:
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def rclone_lsf_recursive(remote_path: str) -> list[str]:
    """Run `rclone lsf -R` to get all files recursively in one call. Much faster than per-folder ls."""
    cmd = ["rclone", "lsf", "-R", f"{RCLONE_REMOTE}:{remote_path}", "--timeout", "600s"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=660)
        if result.returncode != 0:
            print(f"  [WARN] rclone lsf -R failed for {remote_path}: {result.stderr.strip()}", file=sys.stderr)
            return []
        return result.stdout.splitlines()
    except subprocess.TimeoutExpired:
        print(f"  [WARN] rclone lsf -R timed out for {remote_path}", file=sys.stderr)
        return []


def main():
    parser = argparse.ArgumentParser(description="Scan MEGA for scene folders missing Description .docx files.")
    parser.add_argument("--force", action="store_true",
                        help="Scan all folders, ignoring the 30-day recency filter")
    args = parser.parse_args()

    scanned_at = datetime.now().isoformat(timespec="seconds")
    scenes = []

    print(f"Scan started at {scanned_at}")
    if args.force:
        print("Mode: FORCE (scanning all folders)")
    else:
        print(f"Mode: recent only (last {RECENT_DAYS} days)")
    print()

    for studio, mega_path in STUDIOS.items():
        print(f"[{studio}] Single recursive listing of {mega_path}…", flush=True)

        # ONE rclone call per studio — get all files recursively
        all_files = rclone_lsf_recursive(mega_path)
        if not all_files:
            print(f"  No files found (or error).")
            continue

        # Group files by scene folder (first path component)
        # e.g. "VRH0756/Description/file.docx" → scene="VRH0756", path="Description/file.docx"
        scene_files = {}  # scene_folder → [relative_paths]
        for f in all_files:
            f = f.replace("\\", "/")
            parts = f.split("/", 1)
            if len(parts) == 2:
                scene_folder = parts[0]
                scene_files.setdefault(scene_folder, []).append(parts[1])

        # Filter out non-scene folders (Videos, Legal, Storyboard, etc.)
        _SKIP_FOLDERS = {"Videos", "Legal", "Storyboard", "Photos", "Description",
                         "Brand", "Dump", "SYNC", "Backup", "Models"}
        scene_files = {k: v for k, v in scene_files.items() if k not in _SKIP_FOLDERS}

        # Also get folder mtimes from lsd (one call, already fast for top-level dirs)
        lsd_lines = rclone_lsd(mega_path)
        folder_mtimes = {}
        for line in lsd_lines:
            parsed = parse_lsd_line(line)
            if parsed:
                folder_mtimes[parsed[0]] = parsed[1]

        # Filter to recent folders
        in_scope = []
        for folder_name in sorted(scene_files.keys()):
            mtime_str = folder_mtimes.get(folder_name, "")
            if args.force or is_recent(mtime_str, RECENT_DAYS):
                in_scope.append((folder_name, mtime_str))

        print(f"  {len(scene_files)} total folders, {len(in_scope)} in scope, {len(all_files)} files indexed")

        for folder_name, mtime_str in in_scope:
            file_paths = scene_files.get(folder_name, [])
            has_desc = has_description(file_paths)
            female, male = extract_talents(file_paths)

            # Check subfolder statuses
            has_videos = any(p.startswith("Videos/") and not p.endswith("/") for p in file_paths)
            has_thumbnail = any(p.startswith("Video Thumbnail/") and not p.endswith("/") for p in file_paths)
            # Fallback: MEGA API bug drops files inside Video Thumbnail/ but keeps the dir entry.
            # If the directory exists, assume a thumbnail is present.
            if not has_thumbnail:
                has_thumbnail = any(p == "Video Thumbnail/" for p in file_paths)
            has_photos = any(p.startswith("Photos/") and not p.endswith("/") for p in file_paths)
            has_storyboard = any(p.startswith("Storyboard/") and not p.endswith("/") for p in file_paths)

            # Count files per subfolder
            video_count = sum(1 for p in file_paths if p.startswith("Videos/") and not p.endswith("/"))
            storyboard_count = sum(1 for p in file_paths if p.startswith("Storyboard/") and not p.endswith("/"))

            status = "OK" if has_desc else "MISSING"
            name_info = f" [{female}{'/' + male if male else ''}]" if female else ""
            print(f"  {folder_name}… {status}{name_info}")

            # Collect file paths by subfolder for naming validation
            desc_files = [p for p in file_paths if p.startswith("Description/") and not p.endswith("/")]
            video_files = [p for p in file_paths if p.startswith("Videos/") and not p.endswith("/")]
            thumb_files = [p for p in file_paths if p.startswith("Video Thumbnail/") and not p.endswith("/")]
            photo_files = [p for p in file_paths if p.startswith("Photos/") and not p.endswith("/")]
            story_files = [p for p in file_paths if p.startswith("Storyboard/") and not p.endswith("/")]

            scenes.append({
                "scene_id":        folder_name,
                "studio":          studio,
                "has_description": has_desc,
                "has_videos":      has_videos,
                "has_thumbnail":   has_thumbnail,
                "has_photos":      has_photos,
                "has_storyboard":  has_storyboard,
                "video_count":     video_count,
                "storyboard_count": storyboard_count,
                "folder_mtime":    mtime_str,
                "female":          female,
                "male":            male,
                "files": {
                    "description": desc_files,
                    "videos": video_files,
                    "thumbnail": thumb_files,
                    "photos": photo_files,
                    "storyboard": story_files,
                },
            })

        print()

    # Sort: missing first, then by scene_id
    scenes.sort(key=lambda s: (s["has_description"], s["scene_id"]))

    output = {
        "scanned_at": scanned_at,
        "scenes":     scenes,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))

    missing = sum(1 for s in scenes if not s["has_description"])
    total = len(scenes)
    print(f"Done. {missing}/{total} scenes missing descriptions.")
    print(f"Output written to: {OUTPUT_FILE}")

    # Deploy to Windows so the app can read it immediately
    win_dest = "andre@100.90.90.68:C:/Users/andre/eclatech-hub/mega_scan.json"
    ssh_key  = str(Path.home() / ".ssh" / "id_ed25519_win")
    result = subprocess.run(
        ["scp", "-i", ssh_key, str(OUTPUT_FILE), win_dest],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("Deployed to Windows.")
    else:
        print(f"SCP to Windows failed: {result.stderr.strip()}")


if __name__ == "__main__":
    main()
