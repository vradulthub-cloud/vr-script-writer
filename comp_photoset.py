#!/usr/bin/env python3
"""
comp_photoset.py — Compilation Photoset Builder

Downloads raw photo ZIPs from MEGA for each scene in a compilation,
selects 7 evenly-spaced photos per performer for Scene Photos and
3 for Storyboard, then produces the standard folder structure:

    {COMP_ID}/
    ├── Raw/
    │   ├── Scene Photos/    ← 7 per performer, original filenames
    │   └── Storyboard/      ← 3 per performer (1st, mid, last), original filenames
    └── Web/
        ├── Scene Photos/    ← all renumbered VariousHostess-{FirstPerformer}-Photos_NNN.jpg
        └── Storyboard/      ← storyboard renumbered same pattern

Web images are the same resolution but saved at lower JPEG quality (~55).

Usage:
    python3 comp_photoset.py --comp-id VRH0739 \\
        --scenes VRH0650,VRH0612,VRH0580 \\
        --output ~/Desktop/Compilations

    The --scenes are the Grail IDs of the individual scenes whose photos
    will be pulled into the compilation.

Requirements:
    pip install Pillow boto3
    S4 creds available via s4_client (~/.config/eclatech/s4.env or NSSM env)
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow not installed — run: pip install Pillow")
    sys.exit(1)

# ── Logo paths ────────────────────────────────────────────────────────────────
LOGO_DIR = os.path.join(os.path.dirname(__file__), "comp_logos")
LOGOS = {
    "VRH":  os.path.join(LOGO_DIR, "VRH.png"),
    "FPVR": os.path.join(LOGO_DIR, "FPVR.png"),
    "VRA":  os.path.join(LOGO_DIR, "VRA.png"),
    "NJOI": os.path.join(LOGO_DIR, "NJOI.png"),
}

import s4_client

# Web JPEG quality — matches the ~8-9% file-size ratio seen in real photosets
WEB_JPEG_QUALITY = 55


# ── MEGA S4 helpers ───────────────────────────────────────────────────────────

def get_studio(grail_id: str) -> str:
    m = re.match(r'^([A-Za-z]+)', grail_id)
    return m.group(1).upper() if m else ""


def download_photo_zip(grail_id: str, tmp_dir: str) -> str:
    """Download the Photos ZIP for a scene from S4. Returns local zip path.

    Picks the largest ZIP under the scene's Photos/ prefix — some scenes
    have multiple (e.g. NJOI0001 has both `NJOI0001.zip` and `_NJOI0001.zip`)
    and the underscore-prefix version is typically a higher-res master.
    """
    studio = get_studio(grail_id)
    if not studio:
        raise RuntimeError(f"Could not parse studio from grail_id {grail_id!r}")
    sid = s4_client.normalize_scene_id(grail_id)
    prefix = f"{sid}/Photos/"
    zips = []
    # Cover both casings — scan_mega.py canonicalizes to uppercase but a few
    # VRH scenes still have lowercase prefixes in S4 until rename runs.
    for prefix_form in (prefix, prefix.lower()):
        for obj in s4_client.list_objects(studio, prefix=prefix_form):
            if obj["key"].lower().endswith(".zip"):
                zips.append(obj)
        if zips:
            break

    if not zips:
        raise RuntimeError(f"No Photos ZIP found in s4 for {grail_id}")

    chosen = max(zips, key=lambda o: o["size"])
    zip_name = os.path.basename(chosen["key"])
    print(f"  Downloading {zip_name} ({chosen['size'] / 1e6:.1f} MB) ...")
    dst = os.path.join(tmp_dir, f"{grail_id}.zip")
    s4_client.get_object(studio, chosen["key"], dst)
    return dst


# ── Photo extraction ─────────────────────────────────────────────────────────

def _extract_performer(filename: str) -> str:
    """
    Extract the female performer name from a photo filename.
    Handles: 'AndiAvalon-MikeMancini-Photos_003.jpg'  → 'AndiAvalon'
             'AnissaKate-Solo-Photos_014.jpg'          → 'AnissaKate'
    """
    base = os.path.basename(filename)
    m = re.match(r'^([A-Za-z]+)-', base)
    return m.group(1) if m else base


def extract_scene_photos(zip_path: str) -> dict[str, list[str]]:
    """
    Extract a scene's ZIP and return Raw/Scene Photos grouped by performer.
    Returns: {performer_name: [path1, path2, ...]} sorted by filename.
    """
    extract_dir = zip_path.replace(".zip", "_ex")
    os.makedirs(extract_dir, exist_ok=True)

    by_performer: dict[str, list[str]] = {}

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()

        def is_raw_scene(p):
            pl = p.lower()
            return ("raw" in pl and "scene" in pl
                    and pl.endswith((".jpg", ".jpeg"))
                    and not os.path.basename(p).startswith("."))

        candidates = sorted(filter(is_raw_scene, names))
        if not candidates:
            # Fallback: any JPG not in Storyboard
            def is_any_scene(p):
                pl = p.lower()
                return (pl.endswith((".jpg", ".jpeg"))
                        and "storyboard" not in pl
                        and not os.path.basename(p).startswith("."))
            candidates = sorted(filter(is_any_scene, names))

        if not candidates:
            raise RuntimeError(f"No scene photos found in {zip_path}")

        for p in candidates:
            out_path = os.path.join(extract_dir, os.path.basename(p))
            with zf.open(p) as src, open(out_path, "wb") as dst:
                dst.write(src.read())
            performer = _extract_performer(p)
            by_performer.setdefault(performer, []).append(out_path)

    # Sort each performer's photos by filename
    for perf in by_performer:
        by_performer[perf].sort()

    return by_performer


def select_photos(photos: list[str], n: int) -> list[str]:
    """Pick n evenly-spaced photos from a sorted list."""
    total = len(photos)
    if total <= n:
        return list(photos)
    indices = [int(i * (total - 1) / (n - 1)) for i in range(n)]
    return [photos[i] for i in indices]


def select_storyboard(scene_picks: list[str]) -> list[str]:
    """Pick 3 from the 7 scene picks: first, middle, last."""
    if len(scene_picks) <= 3:
        return list(scene_picks)
    mid = len(scene_picks) // 2
    return [scene_picks[0], scene_picks[mid], scene_picks[-1]]


# ── Web renaming ─────────────────────────────────────────────────────────────

def save_web_version(src_path: str, dst_path: str):
    """Save a lower-quality JPEG for the Web version (same resolution)."""
    img = Image.open(src_path)
    img.save(dst_path, "JPEG", quality=WEB_JPEG_QUALITY)


# ── Main builder ─────────────────────────────────────────────────────────────

def build_comp_photoset(
    comp_id:    str,
    scene_ids:  list[str],
    output_dir: str,
    first_performer: str | None = None,
) -> str:
    """
    Build a compilation photoset from individual scene photos.

    For each scene ID:
      1. Download Photos ZIP from MEGA
      2. Extract all Raw/Scene Photos grouped by performer
      3. Pick 7 per performer for Scene Photos, 3 for Storyboard

    Output structure:
      {comp_id}/Raw/Scene Photos/   ← 7 per performer, original filenames
      {comp_id}/Raw/Storyboard/     ← 3 per performer, original filenames
      {comp_id}/Web/Scene Photos/   ← renumbered VariousHostess-{First}-Photos_NNN.jpg
      {comp_id}/Web/Storyboard/     ← renumbered same pattern

    Args:
        comp_id: The compilation's Grail ID (e.g. VRH0739)
        scene_ids: List of source scene Grail IDs
        output_dir: Parent directory for output
        first_performer: Override the performer name used in Web filenames.
                         If None, uses the first performer alphabetically.

    Returns: Path to the created compilation folder.
    """
    comp_dir = os.path.join(os.path.expanduser(output_dir), comp_id)
    raw_scene_dir = os.path.join(comp_dir, "Raw", "Scene Photos")
    raw_story_dir = os.path.join(comp_dir, "Raw", "Storyboard")
    web_scene_dir = os.path.join(comp_dir, "Web", "Scene Photos")
    web_story_dir = os.path.join(comp_dir, "Web", "Storyboard")
    for d in (raw_scene_dir, raw_story_dir, web_scene_dir, web_story_dir):
        os.makedirs(d, exist_ok=True)

    # Collect all performers' selected photos across all scenes
    all_scene_picks: list[tuple[str, str]] = []   # (performer, path)
    all_story_picks: list[tuple[str, str]] = []   # (performer, path)
    all_performers: set[str] = set()

    with tempfile.TemporaryDirectory(prefix="comp_dl_") as tmp_dir:
        for scene_id in scene_ids:
            scene_id = scene_id.strip().upper()
            print(f"\n[{scene_id}]")
            try:
                zip_path = download_photo_zip(scene_id, tmp_dir)
                by_performer = extract_scene_photos(zip_path)

                for performer, photos in sorted(by_performer.items()):
                    scene_picks = select_photos(photos, n=7)
                    story_picks = select_storyboard(scene_picks)

                    for p in scene_picks:
                        all_scene_picks.append((performer, p))
                    for p in story_picks:
                        all_story_picks.append((performer, p))
                    all_performers.add(performer)

                    print(f"  {performer}: {len(scene_picks)} scene, {len(story_picks)} storyboard")

                # Delete the zip but keep extracted photos until we're done
                os.remove(zip_path)

            except Exception as e:
                print(f"  FAILED: {e}")

        if not all_scene_picks:
            print("No photos collected!")
            return comp_dir

        # Determine first performer for Web naming
        if not first_performer:
            first_performer = sorted(all_performers)[0]

        # ── Write Raw (original filenames, flat) ──
        for _, src_path in all_scene_picks:
            fname = os.path.basename(src_path)
            shutil.copy2(src_path, os.path.join(raw_scene_dir, fname))

        for _, src_path in all_story_picks:
            fname = os.path.basename(src_path)
            shutil.copy2(src_path, os.path.join(raw_story_dir, fname))

        # ── Write Web (renumbered, lower quality) ──
        web_prefix = f"VariousHostess-{first_performer}-Photos"

        for i, (_, src_path) in enumerate(all_scene_picks, 1):
            web_name = f"{web_prefix}_{i:03d}.jpg"
            save_web_version(src_path, os.path.join(web_scene_dir, web_name))

        for i, (_, src_path) in enumerate(all_story_picks, 1):
            web_name = f"{web_prefix}_{i:03d}.jpg"
            save_web_version(src_path, os.path.join(web_story_dir, web_name))

    # ── Summary ──
    print(f"\n{'='*50}")
    print(f"Compilation: {comp_id}")
    print(f"Performers:  {len(all_performers)}")
    print(f"Raw Scene:   {len(all_scene_picks)} photos")
    print(f"Raw Story:   {len(all_story_picks)} photos")
    print(f"Web Scene:   {len(all_scene_picks)} photos (as VariousHostess-{first_performer})")
    print(f"Web Story:   {len(all_story_picks)} photos")
    print(f"Output:      {comp_dir}")
    return comp_dir


# ── ZIP packaging ────────────────────────────────────────────────────────────

def package_zip(comp_dir: str) -> str:
    """
    Package the compilation folder into a ZIP matching the MEGA format:
    {COMP_ID}/{Raw,Web}/{Scene Photos,Storyboard}/...
    Returns the zip path.
    """
    comp_id = os.path.basename(comp_dir)
    zip_path = comp_dir + ".zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(comp_dir):
            for f in sorted(files):
                full = os.path.join(root, f)
                arcname = os.path.relpath(full, os.path.dirname(comp_dir))
                zf.write(full, arcname)
    print(f"Packaged: {zip_path} ({os.path.getsize(zip_path) / 1024 / 1024:.1f} MB)")
    return zip_path


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build compilation photoset from MEGA")
    parser.add_argument("--comp-id", required=True,
                        help="Compilation Grail ID e.g. VRH0739")
    parser.add_argument("--scenes", required=True,
                        help="Comma-separated source scene Grail IDs")
    parser.add_argument("--output", default="~/Desktop/Compilations",
                        help="Parent output directory")
    parser.add_argument("--first-performer", default=None,
                        help="Override performer name for Web filenames")
    parser.add_argument("--zip", action="store_true",
                        help="Also create a ZIP of the output")
    args = parser.parse_args()

    ids = [g.strip() for g in args.scenes.split(",") if g.strip()]
    comp_dir = build_comp_photoset(
        args.comp_id, ids, args.output,
        first_performer=args.first_performer,
    )
    if args.zip:
        package_zip(comp_dir)
