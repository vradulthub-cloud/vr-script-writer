#!/usr/bin/env python3
"""
scan_mega.py — Scan MEGA S4 buckets for scene folders missing Description files.

Replaces the legacy rclone-based scan against the MEGA cloud account. One bucket
per studio (fpvr/vrh/vra/njoi); keys are bucket-rooted scene IDs (no /Grail/
and no studio prefix). All S4 calls go through s4_client.

Output schema (mega_scan.json) is unchanged so the hub DB and UI are unaffected.

Usage:
    python3 scan_mega.py          # scan only scenes touched in the last 30 days
    python3 scan_mega.py --force  # scan ALL scenes regardless of mtime
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Load S4 creds from the persistent env file (cron-friendly — cron has no shell rc).
ENV_FILE = Path.home() / ".config" / "eclatech" / "s4.env"
if ENV_FILE.exists():
    for _line in ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v)

import s4_client  # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────

DROPBOX_PATH = Path.home() / "Library" / "CloudStorage" / "Dropbox"
OUTPUT_FILE = DROPBOX_PATH / "mega_scan.json"
RECENT_DAYS = 30

WIN_DEST = "andre@100.90.90.68:C:/Users/andre/eclatech-hub/mega_scan.json"
SSH_KEY = str(Path.home() / ".ssh" / "id_ed25519_win")

_DESC_EXTS = (".doc", ".docx", ".txt", ".rtf")

# Studio site codes — used to filter out non-scene top-level prefixes
# (Brand/, Dump/, SYNC/, Legal/, etc. that exist in some buckets).
_SITE_CODES = {"FPVR": "FPVR", "VRH": "VRH", "VRA": "VRA", "NJOI": "NJOI"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def camel_to_spaced(s: str) -> str:
    return re.sub(r"([A-Z])", r" \1", s).strip()


def extract_talents(file_paths: list[str]) -> tuple[str, str]:
    """Pull (female, male) names from the first CamelCase-looking filename.
    Priority: Videos > Storyboard > Photos > Legal."""
    priority = {"Videos": 0, "Storyboard": 1, "Photos": 2, "Legal": 3}
    sorted_paths = sorted(file_paths,
                          key=lambda p: priority.get(p.split("/")[0], 99))
    for p in sorted_paths:
        folder = p.split("/", 1)[0] if "/" in p else ""
        if folder not in priority:
            continue
        basename = p.split("/")[-1].rsplit(".", 1)[0]
        basename = re.sub(r"_\d+$", "", basename)  # strip trailing _001 etc
        names: list[str] = []
        for part in basename.split("-"):
            if re.match(r"^[A-Z][a-z]+[A-Z]", part):
                names.append(camel_to_spaced(part))
            else:
                break
        if names:
            return names[0], (names[1] if len(names) > 1 else "")
    return "", ""


def has_description(file_paths: list[str]) -> bool:
    for p in file_paths:
        if p.startswith("Description/") and p.lower().endswith(_DESC_EXTS):
            return True
    return False


def is_recent(mtime, days: int) -> bool:
    if not mtime:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return mtime >= cutoff


def is_scene_prefix(raw: str, studio: str) -> bool:
    """Does `raw` (the first key segment) look like a scene ID for `studio`?"""
    site = _SITE_CODES[studio]
    return bool(re.fullmatch(rf"{site}\d+", raw, re.IGNORECASE))


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan MEGA S4 buckets for scene folders missing Description docs."
    )
    parser.add_argument("--force", action="store_true",
                        help="Scan all scenes, ignoring the 30-day recency filter")
    args = parser.parse_args()

    scanned_at = datetime.now().isoformat(timespec="seconds")
    scenes: list[dict] = []

    print(f"Scan started at {scanned_at}")
    print(f"Mode: {'FORCE (all scenes)' if args.force else f'recent only (last {RECENT_DAYS}d)'}")
    print()

    # Carry forward older scenes that fall outside the recency window so the
    # output doesn't shrink each non-force run (would wipe has_* flags in DB).
    prior_by_id: dict[str, dict] = {}
    if not args.force and OUTPUT_FILE.exists():
        try:
            prior = json.loads(OUTPUT_FILE.read_text())
            for s in prior.get("scenes") or []:
                if s.get("scene_id"):
                    prior_by_id[s["scene_id"]] = s
            if prior_by_id:
                print(f"Loaded {len(prior_by_id)} prior scenes to preserve out-of-scope folders.")
                print()
        except Exception as exc:
            print(f"  [WARN] could not load prior scan: {exc}", file=sys.stderr)

    # Track casing collisions (e.g. VRH0500 + vrh0500 in same bucket would
    # canonicalize to the same scene). Warn loudly — that's data corruption,
    # not just a casing quirk.
    seen_canonical: dict[str, str] = {}

    for studio in s4_client.STUDIO_BUCKETS:
        bucket = s4_client.STUDIO_BUCKETS[studio]
        print(f"[{studio}] Listing bucket {bucket}…", flush=True)

        try:
            objects = list(s4_client.list_objects(studio))
        except Exception as exc:
            print(f"  [ERR] list_objects({studio}) failed: {exc}", file=sys.stderr)
            continue

        # Group objects by scene id (canonicalized).
        by_scene: dict[str, dict] = defaultdict(
            lambda: {"files": [], "mtime": None, "raw_casings": set()}
        )
        skipped_non_scene = 0
        for obj in objects:
            key = obj["key"]
            # Skip 0-byte folder markers (key ends in /).
            if key.endswith("/") and obj["size"] == 0:
                continue
            head, _, rel = key.partition("/")
            if not rel or not is_scene_prefix(head, studio):
                skipped_non_scene += 1
                continue
            try:
                canon = s4_client.normalize_scene_id(head)
            except ValueError:
                skipped_non_scene += 1
                continue
            entry = by_scene[canon]
            entry["files"].append(rel)
            entry["raw_casings"].add(head)
            mt = obj["last_modified"]
            if entry["mtime"] is None or mt > entry["mtime"]:
                entry["mtime"] = mt

        print(f"  {len(by_scene)} scene folders, {len(objects)} objects, "
              f"{skipped_non_scene} non-scene keys skipped")

        # Filter to recent + canonical-collision detection.
        in_scope: list[tuple[str, dict, str]] = []
        for canon, entry in by_scene.items():
            mtime = entry["mtime"]
            mtime_str = mtime.strftime("%Y-%m-%d %H:%M:%S") if mtime else ""
            if canon in seen_canonical:
                # Should never happen — same canonical scene-id seen across
                # two studios would mean a wildly miscategorized bucket.
                print(f"  [WARN] {canon} already claimed by {seen_canonical[canon]}; skipping", file=sys.stderr)
                continue
            if len(entry["raw_casings"]) > 1:
                cases = sorted(entry["raw_casings"])
                print(f"  [WARN] {canon} has multiple casings on disk: {cases}", file=sys.stderr)
            if args.force or is_recent(mtime, RECENT_DAYS):
                seen_canonical[canon] = studio
                in_scope.append((canon, entry, mtime_str))

        print(f"  {len(in_scope)} in scope")

        for canon, entry, mtime_str in in_scope:
            file_paths = entry["files"]
            has_desc       = has_description(file_paths)
            female, male   = extract_talents(file_paths)
            has_videos     = any(p.startswith("Videos/")          for p in file_paths)
            has_thumbnail  = any(p.startswith("Video Thumbnail/") for p in file_paths)
            has_photos     = any(p.startswith("Photos/")          for p in file_paths)
            has_storyboard = any(p.startswith("Storyboard/")      for p in file_paths)
            video_count      = sum(1 for p in file_paths if p.startswith("Videos/"))
            storyboard_count = sum(1 for p in file_paths if p.startswith("Storyboard/"))

            status = "OK" if has_desc else "MISSING"
            name_info = f" [{female}{'/' + male if male else ''}]" if female else ""
            print(f"  {canon}… {status}{name_info}")

            scenes.append({
                "scene_id":        canon,
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
                    "description": [p for p in file_paths if p.startswith("Description/")],
                    "videos":      [p for p in file_paths if p.startswith("Videos/")],
                    "thumbnail":   [p for p in file_paths if p.startswith("Video Thumbnail/")],
                    "photos":      [p for p in file_paths if p.startswith("Photos/")],
                    "storyboard":  [p for p in file_paths if p.startswith("Storyboard/")],
                },
            })

        print()

    # Carry forward prior entries for scenes not touched this run so older
    # scenes keep their last-known asset state.
    if prior_by_id:
        touched = {s["scene_id"] for s in scenes}
        carried = sum(1 for sid in prior_by_id if sid not in touched)
        for sid, prev in prior_by_id.items():
            if sid not in touched:
                scenes.append(prev)
        if carried:
            print(f"Carried forward {carried} scenes from prior scan.")

    scenes.sort(key=lambda s: (s["has_description"], s["scene_id"]))

    output = {"scanned_at": scanned_at, "scenes": scenes}
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))

    missing = sum(1 for s in scenes if not s["has_description"])
    print(f"Done. {missing}/{len(scenes)} scenes missing descriptions.")
    print(f"Output: {OUTPUT_FILE}")

    # Deploy to Windows so the API service reads the same scan.
    result = subprocess.run(
        ["scp", "-i", SSH_KEY, str(OUTPUT_FILE), WIN_DEST],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("Deployed to Windows.")
    else:
        print(f"SCP to Windows failed: {result.stderr.strip()}")


if __name__ == "__main__":
    main()
