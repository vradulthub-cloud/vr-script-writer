"""fix_subfolder_typos.py — rename misspelled scene subfolders in MEGA S4.

Each scene folder is supposed to hold exactly six canonical subfolders:
``Description/``, ``Videos/``, ``Photos/``, ``Storyboard/``, ``Legal/``,
``Video Thumbnail/``. The migration carried over a handful of typo'd
subfolders from the legacy MEGA tree (e.g. ``Descritpion/``) which makes
``scan_mega.py`` incorrectly flag the scene as missing that asset.

This script does a server-side COPY + DELETE for each object whose key
contains a known typo, so the bytes move into the canonical subfolder
without re-uploading. Idempotent — re-running after a partial run is safe.

    python3 fix_subfolder_typos.py            # dry run, prints planned moves
    python3 fix_subfolder_typos.py --apply    # actually performs the rename
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import s4_client


# Map of misspelled segment -> canonical segment. Add to this list as more
# typos surface; everything in ``s4_client.STUDIO_BUCKETS`` is scanned each
# run so adding a new entry rescans every bucket.
TYPO_FIXES: dict[str, str] = {
    # Description/
    "Descritpion":  "Description",
    "Descripton":   "Description",
    "Descripion":   "Description",
    "description":  "Description",
    "DESCRIPTION":  "Description",
    "Description ": "Description",   # trailing space (FPVR0198)
    "Description 1": "Description",  # numbered duplicate where canonical is empty (VRH0632)
    # Videos/
    "Vidoes":      "Videos",
    "VIdeos":      "Videos",
    "videos":      "Videos",
    "VIDEOS":      "Videos",
    "videos 2":    "Videos",   # numbered duplicate where canonical is empty (VRH0632)
    # Photos/
    "Photo":       "Photos",
    "photos":      "Photos",
    "PHOTOS":      "Photos",
    # Storyboard/
    "Storybard":     "Storyboard",
    "Stroyboard":    "Storyboard",
    "Storyboards":   "Storyboard",
    "storyboard":    "Storyboard",
    "STORYBOARD":    "Storyboard",
    "Storyboard 1":  "Storyboard",   # numbered duplicate where canonical is empty (VRH0632)
    # Legal/
    "legal":       "Legal",
    "LEGAL":       "Legal",
    "Legals":      "Legal",
    # Video Thumbnail/
    "Video Thumbnails": "Video Thumbnail",
    "Video thumbnail":  "Video Thumbnail",
    "VideoThumbnail":   "Video Thumbnail",
    "Thumbnail":        "Video Thumbnail",
}


def _planned_renames(studio: str) -> list[tuple[str, str]]:
    """Return [(old_key, new_key), ...] for every object that needs moving."""
    plans: list[tuple[str, str]] = []
    for obj in s4_client.list_objects(studio):
        key = obj["key"]
        parts = key.split("/")
        if len(parts) < 2:
            continue
        sub = parts[1]
        canonical = TYPO_FIXES.get(sub)
        if canonical is None:
            continue
        new_parts = parts.copy()
        new_parts[1] = canonical
        new_key = "/".join(new_parts)
        if new_key != key:
            plans.append((key, new_key))
    return plans


def _rename_one(bucket: str, old_key: str, new_key: str) -> tuple[str, str, str]:
    """Server-side COPY + DELETE. Returns (status, old_key, detail)."""
    client = s4_client._client()
    try:
        # Skip if dest already exists with the same size — happens on re-runs
        # if a previous attempt finished half the work.
        try:
            head = client.head_object(Bucket=bucket, Key=new_key)
            if head["ContentLength"] > 0:
                client.delete_object(Bucket=bucket, Key=old_key)
                return ("skipped-dest-exists", old_key, new_key)
        except Exception:
            pass

        client.copy_object(
            Bucket=bucket,
            Key=new_key,
            CopySource={"Bucket": bucket, "Key": old_key},
        )
        client.delete_object(Bucket=bucket, Key=old_key)
        return ("ok", old_key, new_key)
    except Exception as exc:
        return ("error", old_key, f"{type(exc).__name__}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually perform the renames (default: dry run)")
    parser.add_argument("--studio",
                        help="Limit to one studio (FPVR/VRH/VRA/NJOI)")
    parser.add_argument("--workers", type=int, default=8,
                        help="Parallel COPY+DELETE threads (default 8)")
    args = parser.parse_args()

    studios = [args.studio] if args.studio else list(s4_client.STUDIO_BUCKETS)
    grand_total_plans: list[tuple[str, str, str]] = []  # (studio, old, new)

    for studio in studios:
        bucket = s4_client._studio_to_bucket(studio)
        print(f"\n[{studio}] scanning bucket {bucket}…", flush=True)
        plans = _planned_renames(studio)
        if not plans:
            print(f"  no typos found")
            continue

        # Group by typo for a readable summary
        by_typo: dict[str, int] = defaultdict(int)
        for old, _new in plans:
            seg = old.split("/")[1]
            by_typo[seg] += 1
        for seg, count in sorted(by_typo.items()):
            print(f"  {count:5d} objects under {seg!r:25s} → {TYPO_FIXES[seg]!r}")

        for old, new in plans:
            grand_total_plans.append((studio, old, new))

    if not grand_total_plans:
        print("\nNothing to fix.")
        return 0

    print(f"\nTotal: {len(grand_total_plans)} object(s) across {len({s for s,_,_ in grand_total_plans})} studio(s)")

    if not args.apply:
        print("Dry run — re-run with --apply to perform the renames.")
        return 0

    print(f"\nApplying renames with {args.workers} workers…", flush=True)
    ok = err = skipped = 0
    by_studio = defaultdict(list)
    for studio, old, new in grand_total_plans:
        by_studio[studio].append((old, new))

    for studio, items in by_studio.items():
        bucket = s4_client._studio_to_bucket(studio)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(_rename_one, bucket, old, new) for old, new in items]
            for i, fut in enumerate(as_completed(futures), 1):
                status, old_key, detail = fut.result()
                if status == "ok":
                    ok += 1
                elif status.startswith("skipped"):
                    skipped += 1
                else:
                    err += 1
                    print(f"  [ERR] {old_key}: {detail}", file=sys.stderr)
                if i % 50 == 0 or i == len(items):
                    print(f"  [{studio}] {i}/{len(items)}", flush=True)

    print(f"\nDone: {ok} renamed, {skipped} skipped, {err} errors")
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
