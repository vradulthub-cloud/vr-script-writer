"""
mega_scan_worker.py — Scan MEGA via MEGAcmd on Windows.

Called by the Refresh button in the Asset Tracker. Uses `mega-ls -R` to
list all scene folders, then writes mega_scan.json in the same format
as scan_mega.py (Mac rclone version) so asset_tracker.py can read it.

Usage:
    # From Streamlit (imported):
    import mega_scan_worker
    mega_scan_worker.run_scan()

    # Standalone:
    python mega_scan_worker.py
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

MEGACMD_DIR = Path(os.environ.get(
    "MEGACMD_DIR",
    r"C:\Users\andre\AppData\Local\MEGAcmd",
))
MEGA_LS = str(MEGACMD_DIR / "mega-ls.bat")

STUDIOS = {
    "FPVR": "/Grail/FPVR",
    "VRH":  "/Grail/VRH",
    "VRA":  "/Grail/VRA",
    "NJOI": "/Grail/NNJOI",
}

OUTPUT_FILE = Path(os.path.dirname(__file__)) / "mega_scan.json"

# Scene ID pattern: letters + digits (FPVR0001, VRH0640, NJOI0001, etc.)
_SCENE_RE = re.compile(r'^[A-Za-z]+\d+$')

# Subfolders we track as assets
_ASSET_FOLDERS = {"Description", "Videos", "Video Thumbnail", "Photos", "Storyboard", "Legal"}


# ── Helpers (same logic as scan_mega.py) ──────────────────────────────────────

def _camel_to_spaced(s: str) -> str:
    """'ClaraTrinity' -> 'Clara Trinity'"""
    return re.sub(r'([A-Z])', r' \1', s).strip()


def _extract_talents(file_paths: list[str]) -> tuple[str, str]:
    """Extract female/male talent names from filenames."""
    priority = {"Videos": 0, "Storyboard": 1, "Photos": 2, "Legal": 3}
    sorted_paths = sorted(
        file_paths,
        key=lambda p: priority.get(p.split("/")[0], 99),
    )
    for p in sorted_paths:
        folder = p.split("/")[0] if "/" in p else ""
        if folder not in ("Videos", "Storyboard", "Photos", "Legal"):
            continue
        basename = p.split("/")[-1].rsplit(".", 1)[0]
        basename = re.sub(r'_\d+$', '', basename)
        parts = basename.split("-")
        names = []
        for part in parts:
            if re.match(r'^[A-Z][a-z]+[A-Z]', part):
                names.append(_camel_to_spaced(part))
            else:
                break
        if names:
            return names[0], names[1] if len(names) > 1 else ""
    return "", ""


_DESC_EXTS = (".doc", ".docx", ".txt", ".rtf")


def _has_description(file_paths: list[str]) -> bool:
    """Check if any file in a Description folder is a text/document type (.doc, .docx, .txt, .rtf)."""
    return any(
        p.startswith("Description/") and p.lower().endswith(_DESC_EXTS)
        for p in file_paths
    )


# ── Tree parser ───────────────────────────────────────────────────────────────

def _parse_mega_ls_tree(output: str) -> dict[str, list[str]]:
    """
    Parse `mega-ls -R` tree output into {scene_id: [relative/file/paths]}.

    mega-ls -R output format:
        SCENE_ID          <- level 0 (no tabs), scene folder
            Subfolder     <- level 1 (1 tab)
                file.ext  <- level 2 (2 tabs)
    """
    scenes: dict[str, list[str]] = {}
    current_scene = None
    current_subfolder = None

    for line in output.splitlines():
        if not line.strip():
            continue

        # Count leading tabs
        stripped = line.lstrip('\t')
        level = len(line) - len(stripped)
        name = stripped.strip()
        if not name:
            continue

        if level == 0:
            # Top-level: scene folder or non-scene folder
            if _SCENE_RE.match(name):
                current_scene = name
                scenes.setdefault(current_scene, [])
            else:
                current_scene = None
            current_subfolder = None
        elif level == 1 and current_scene is not None:
            # Subfolder within a scene
            current_subfolder = name
        elif level == 2 and current_scene is not None and current_subfolder is not None:
            # File within a subfolder
            scenes[current_scene].append(f"{current_subfolder}/{name}")

    return scenes


# ── Scanner ───────────────────────────────────────────────────────────────────

def _mega_ls_recursive(mega_path: str) -> str:
    """Run mega-ls -R and return stdout. Raises on failure."""
    cmd = [MEGA_LS, "-R", mega_path]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=600,
    )
    stderr = result.stderr.strip() if result.stderr else ""
    if "Not logged in" in stderr:
        raise RuntimeError("MEGA session expired. Log in via MEGAcmd on Windows.")
    if result.returncode != 0 and not result.stdout.strip():
        raise RuntimeError(f"mega-ls failed for {mega_path}: {stderr}")
    return result.stdout


def run_scan(progress_callback=None) -> dict:
    """
    Scan all studios via MEGAcmd and write mega_scan.json.

    Args:
        progress_callback: optional callable(message: str) for UI updates

    Returns:
        The scan result dict (also written to disk).

    Raises:
        RuntimeError: if MEGAcmd is not available or MEGA session is expired.
    """
    # Verify MEGAcmd exists
    if not Path(MEGA_LS).exists():
        raise RuntimeError(
            f"MEGAcmd not found at {MEGA_LS}. "
            "Install MEGAcmd or set MEGACMD_DIR environment variable."
        )

    scanned_at = datetime.now().isoformat(timespec="seconds")
    all_scenes = []
    errors = []

    for studio, mega_path in STUDIOS.items():
        if progress_callback:
            progress_callback(f"Scanning {studio}...")
        try:
            output = _mega_ls_recursive(mega_path + "/")
        except (subprocess.TimeoutExpired, RuntimeError) as e:
            errors.append(f"{studio}: {e}")
            print(f"[WARN] {studio} scan failed: {e}", file=sys.stderr)
            continue

        scene_files = _parse_mega_ls_tree(output)
        print(f"[{studio}] {len(scene_files)} scenes found")

        for scene_id, file_paths in sorted(scene_files.items()):
            has_desc = _has_description(file_paths)
            female, male = _extract_talents(file_paths)

            has_videos = any(p.startswith("Videos/") for p in file_paths)
            has_thumbnail = any(
                p.startswith("Video Thumbnail/") for p in file_paths
            )
            has_photos = any(p.startswith("Photos/") for p in file_paths)
            has_storyboard = any(p.startswith("Storyboard/") for p in file_paths)

            video_count = sum(1 for p in file_paths if p.startswith("Videos/"))
            storyboard_count = sum(
                1 for p in file_paths if p.startswith("Storyboard/")
            )

            desc_files = [p for p in file_paths if p.startswith("Description/")]
            video_files = [p for p in file_paths if p.startswith("Videos/")]
            thumb_files = [p for p in file_paths if p.startswith("Video Thumbnail/")]
            photo_files = [p for p in file_paths if p.startswith("Photos/")]
            story_files = [p for p in file_paths if p.startswith("Storyboard/")]

            all_scenes.append({
                "scene_id":         scene_id,
                "studio":           studio,
                "has_description":  has_desc,
                "has_videos":       has_videos,
                "has_thumbnail":    has_thumbnail,
                "has_photos":       has_photos,
                "has_storyboard":   has_storyboard,
                "video_count":      video_count,
                "storyboard_count": storyboard_count,
                "female":           female,
                "male":             male,
                "folder_mtime":     "",
                "files": {
                    "description": desc_files,
                    "videos":      video_files,
                    "thumbnail":   thumb_files,
                    "photos":      photo_files,
                    "storyboard":  story_files,
                },
            })

    if not all_scenes and errors:
        raise RuntimeError(
            "MEGA scan failed for all studios:\n" + "\n".join(errors)
        )

    # Guard: never overwrite a populated scan with empty results.
    # If mega-ls returned no parseable scenes but didn't error, something
    # is wrong (session issue, empty output, parse failure). Keep existing data.
    if not all_scenes:
        msg = "MEGA scan returned 0 scenes without errors — keeping existing data."
        print(f"[WARN] {msg}", file=sys.stderr)
        if progress_callback:
            progress_callback(msg)
        # Return existing data so the UI doesn't show stale-but-valid as broken
        try:
            if OUTPUT_FILE.exists():
                return json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"scanned_at": scanned_at, "scenes": []}

    # Sort: missing descriptions first, then by scene_id
    all_scenes.sort(key=lambda s: (s["has_description"], s["scene_id"]))

    result = {"scanned_at": scanned_at, "scenes": all_scenes}

    # Atomic write: temp file then replace
    fd, tmp_path = tempfile.mkstemp(
        dir=str(OUTPUT_FILE.parent), suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(OUTPUT_FILE))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    missing = sum(1 for s in all_scenes if not s["has_description"])
    total = len(all_scenes)
    msg = f"Done. {total} scenes scanned, {missing} missing descriptions."
    if errors:
        msg += f" Warnings: {'; '.join(errors)}"
    print(msg)

    if progress_callback:
        progress_callback(msg)

    return result


if __name__ == "__main__":
    run_scan(progress_callback=lambda m: print(m))
