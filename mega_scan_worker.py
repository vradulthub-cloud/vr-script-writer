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

# Each studio can have multiple paths (primary + backup). Older VRH/VRA
# scenes live in /Grail/Backup/{studio}/. Skipping the backup paths means
# ~175 VRH + ~375 VRA scenes silently look "missing" in the catalog after
# any on-demand scan — same issue scan_mega.py had before this was fixed.
STUDIOS: dict[str, list[str]] = {
    "FPVR": ["/Grail/FPVR"],
    "VRH":  ["/Grail/VRH",  "/Grail/Backup/VRH"],
    "VRA":  ["/Grail/VRA",  "/Grail/Backup/VRA"],
    "NJOI": ["/Grail/NNJOI"],
}

OUTPUT_FILE = Path(os.path.dirname(__file__)) / "mega_scan.json"

# Single-flight lock so hot + cold + on-demand scans can't thrash MEGAcmd.
import threading as _threading
_SCAN_LOCK = _threading.Lock()

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


def _build_scene_dict(scene_id: str, studio: str, file_paths: list[str]) -> dict:
    """Extract the scene dict structure used by both run_scan and run_hot_scan.
    Single source of truth for the scene schema written to mega_scan.json.
    """
    has_desc = _has_description(file_paths)
    female, male = _extract_talents(file_paths)

    has_videos     = any(p.startswith("Videos/") for p in file_paths)
    has_thumbnail  = any(p.startswith("Video Thumbnail/") for p in file_paths)
    has_photos     = any(p.startswith("Photos/") for p in file_paths)
    has_storyboard = any(p.startswith("Storyboard/") for p in file_paths)
    has_legal      = any(p.startswith("Legal/") for p in file_paths)

    video_count      = sum(1 for p in file_paths if p.startswith("Videos/"))
    storyboard_count = sum(1 for p in file_paths if p.startswith("Storyboard/"))
    legal_count      = sum(1 for p in file_paths if p.startswith("Legal/"))

    return {
        "scene_id":         scene_id,
        "studio":           studio,
        "has_description":  has_desc,
        "has_videos":       has_videos,
        "has_thumbnail":    has_thumbnail,
        "has_photos":       has_photos,
        "has_storyboard":   has_storyboard,
        "has_legal":        has_legal,
        "video_count":      video_count,
        "storyboard_count": storyboard_count,
        "legal_count":      legal_count,
        "female":           female,
        "male":             male,
        "folder_mtime":     "",
        "files": {
            "description": [p for p in file_paths if p.startswith("Description/")],
            "videos":      [p for p in file_paths if p.startswith("Videos/")],
            "thumbnail":   [p for p in file_paths if p.startswith("Video Thumbnail/")],
            "photos":      [p for p in file_paths if p.startswith("Photos/")],
            "storyboard":  [p for p in file_paths if p.startswith("Storyboard/")],
            "legal":       [p for p in file_paths if p.startswith("Legal/")],
        },
    }


# Mapping from scene_id prefix → (studio_key, candidate roots). Backup paths
# are tried as fallback for VRH/VRA so the hot-scan finds older scenes that
# live in /Grail/Backup/. Primary path is first — if the scene exists there,
# we use it without making the second call.
_STUDIO_FROM_PREFIX: dict[str, tuple[str, list[str]]] = {
    "FPVR": ("FPVR", ["/Grail/FPVR"]),
    "VRH":  ("VRH",  ["/Grail/VRH",  "/Grail/Backup/VRH"]),
    "VRA":  ("VRA",  ["/Grail/VRA",  "/Grail/Backup/VRA"]),
    "NJOI": ("NJOI", ["/Grail/NNJOI"]),
}


def _studio_for_scene_id(scene_id: str) -> tuple[str, list[str]] | None:
    """FPVR0401 → ('FPVR', ['/Grail/FPVR']). None if unrecognized prefix."""
    for prefix, info in _STUDIO_FROM_PREFIX.items():
        if scene_id.startswith(prefix):
            return info
    return None


def run_hot_scan(scene_ids: list[str], progress_callback=None) -> dict:
    """
    Scan only the given scene folders and merge their state into mega_scan.json.

    Much cheaper than run_scan() — a per-scene `mega-ls -R /Grail/VRH/VRH0762`
    takes ~1s. For ~14 hot scenes that's under 20s versus run_scan's 30s+ full
    sweep. Preserves all other scenes in mega_scan.json untouched.

    Thread-safe via _SCAN_LOCK. If the lock is held (another scan in flight),
    skips this tick rather than queueing.

    Args:
        scene_ids: list of scene IDs (e.g. ["VRH0762", "FPVR0393"]) to refresh.
        progress_callback: optional callable(message: str) for UI updates.

    Returns:
        {"scanned_at": iso, "hot_scenes": N, "skipped_locked": bool}
    """
    if not scene_ids:
        return {"scanned_at": "", "hot_scenes": 0, "skipped_locked": False}

    if not Path(MEGA_LS).exists():
        raise RuntimeError(f"MEGAcmd not found at {MEGA_LS}")

    if not _SCAN_LOCK.acquire(blocking=False):
        return {"scanned_at": "", "hot_scenes": 0, "skipped_locked": True}

    try:
        # Load existing scan data; we'll replace only the scanned scenes.
        if OUTPUT_FILE.exists():
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        else:
            existing = {"scanned_at": "", "scenes": []}

        scanned_at = datetime.now().isoformat(timespec="seconds")
        # Index existing scenes by id for O(1) replace
        scenes_by_id = {s["scene_id"]: s for s in existing.get("scenes", [])}

        updated = 0
        for scene_id in scene_ids:
            if progress_callback:
                progress_callback(f"Hot-scanning {scene_id}...")
            info = _studio_for_scene_id(scene_id)
            if not info:
                continue
            studio, studio_roots = info
            # Try primary first, fall back to backup. Stop at first non-empty hit.
            output = ""
            for studio_root in studio_roots:
                scene_path = f"{studio_root}/{scene_id}/"
                try:
                    candidate = _mega_ls_recursive(scene_path)
                except (subprocess.TimeoutExpired, RuntimeError) as e:
                    print(f"[WARN] hot scan failed for {scene_id} at {studio_root}: {e}", file=sys.stderr)
                    continue
                if candidate.strip():
                    output = candidate
                    break
            # mega-ls -R on a specific scene path emits the scene's *subfolders*
            # at level 0 (no scene_id header), so the tree parser — which keys
            # off a level-0 scene row — returns {}. Prepend a synthetic scene
            # header and indent every existing line by one tab so the existing
            # parser sees subfolders at level 1 and files at level 2.
            indented = "\n".join("\t" + ln if ln.strip() else ln for ln in output.splitlines())
            output_with_header = f"{scene_id}\n{indented}"
            scene_files = _parse_mega_ls_tree(output_with_header)
            if scene_id not in scene_files:
                # Folder is empty or doesn't exist — treat as no-op; preserve
                # previous entry if any, otherwise write an empty shell so
                # downstream code can reason about "scanned but nothing there".
                scene_files[scene_id] = []
            scenes_by_id[scene_id] = _build_scene_dict(
                scene_id, studio, scene_files[scene_id],
            )
            updated += 1

        merged = list(scenes_by_id.values())
        merged.sort(key=lambda s: (s.get("has_description", False), s["scene_id"]))

        result = {"scanned_at": scanned_at, "scenes": merged}

        # Atomic write
        fd, tmp_path = tempfile.mkstemp(
            dir=str(OUTPUT_FILE.parent), suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(OUTPUT_FILE))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        return {"scanned_at": scanned_at, "hot_scenes": updated, "skipped_locked": False}
    finally:
        _SCAN_LOCK.release()


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

    # Single-flight: if another scan is in flight, wait instead of starting a
    # second one (full scans can take 30s+ — parallel scans trash MEGAcmd state).
    with _SCAN_LOCK:
        return _run_scan_locked(progress_callback)


def _run_scan_locked(progress_callback=None) -> dict:
    scanned_at = datetime.now().isoformat(timespec="seconds")
    all_scenes = []
    errors = []

    # Load existing scan data so we can preserve per-studio results on failure
    prev_scenes_by_studio: dict[str, list] = {}
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                prev = json.load(f)
            for s in prev.get("scenes", []):
                prev_scenes_by_studio.setdefault(s["studio"], []).append(s)
        except (json.JSONDecodeError, KeyError):
            pass

    for studio, mega_paths in STUDIOS.items():
        if progress_callback:
            progress_callback(f"Scanning {studio}...")
        # Merge results across primary + backup paths. Primary wins on
        # collision (older Backup copy doesn't override fresh asset state).
        scene_files: dict[str, list[str]] = {}
        path_failures: list[str] = []
        for mega_path in mega_paths:
            try:
                output = _mega_ls_recursive(mega_path + "/")
            except (subprocess.TimeoutExpired, RuntimeError) as e:
                path_failures.append(f"{mega_path}: {e}")
                print(f"[WARN] {studio} scan failed for {mega_path}: {e}", file=sys.stderr)
                continue
            for sid, files in _parse_mega_ls_tree(output).items():
                # Case-insensitive dedupe — backup folders sometimes mix
                # casing (vrh0002 vs VRH0485 in /Grail/Backup/VRH).
                if sid not in scene_files and not any(k.lower() == sid.lower() for k in scene_files):
                    scene_files[sid] = files
        # If every path failed, preserve previous data for the whole studio.
        if not scene_files and path_failures:
            errors.extend(path_failures)
            if studio in prev_scenes_by_studio:
                all_scenes.extend(prev_scenes_by_studio[studio])
                print(f"[{studio}] Preserved {len(prev_scenes_by_studio[studio])} scenes from previous scan")
            continue
        if path_failures:
            errors.extend(path_failures)

        # Guard: if scan returned 0 scenes but we had data before, keep the old data
        if not scene_files and studio in prev_scenes_by_studio and prev_scenes_by_studio[studio]:
            errors.append(f"{studio}: scan returned 0 scenes — preserved previous data")
            print(f"[WARN] {studio} returned 0 scenes, preserving {len(prev_scenes_by_studio[studio])} from previous scan", file=sys.stderr)
            all_scenes.extend(prev_scenes_by_studio[studio])
            continue

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
            has_legal = any(p.startswith("Legal/") for p in file_paths)

            video_count = sum(1 for p in file_paths if p.startswith("Videos/"))
            storyboard_count = sum(
                1 for p in file_paths if p.startswith("Storyboard/")
            )
            legal_count = sum(1 for p in file_paths if p.startswith("Legal/"))

            desc_files = [p for p in file_paths if p.startswith("Description/")]
            video_files = [p for p in file_paths if p.startswith("Videos/")]
            thumb_files = [p for p in file_paths if p.startswith("Video Thumbnail/")]
            photo_files = [p for p in file_paths if p.startswith("Photos/")]
            story_files = [p for p in file_paths if p.startswith("Storyboard/")]
            legal_files = [p for p in file_paths if p.startswith("Legal/")]

            all_scenes.append({
                "scene_id":         scene_id,
                "studio":           studio,
                "has_description":  has_desc,
                "has_videos":       has_videos,
                "has_thumbnail":    has_thumbnail,
                "has_photos":       has_photos,
                "has_storyboard":   has_storyboard,
                "has_legal":        has_legal,
                "video_count":      video_count,
                "storyboard_count": storyboard_count,
                "legal_count":      legal_count,
                "female":           female,
                "male":             male,
                "folder_mtime":     "",
                "files": {
                    "description": desc_files,
                    "videos":      video_files,
                    "thumbnail":   thumb_files,
                    "photos":      photo_files,
                    "storyboard":  story_files,
                    "legal":       legal_files,
                },
            })

    if not all_scenes and errors:
        raise RuntimeError(
            "MEGA scan failed for all studios:\n" + "\n".join(errors)
        )

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
