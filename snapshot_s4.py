#!/usr/bin/env python3
"""snapshot_s4.py — Daily key-list tripwire for the four S4 buckets.

MEGA S4 doesn't support bucket versioning (verified via boto3 — the
``GetBucketVersioning`` op returns NotImplemented). That means a delete is
permanent. To compensate, this script writes a daily snapshot of every
object in every bucket (key + size + etag + mtime) so:

  * Unauthorized or accidental deletes are detectable within 24 h.
  * A diff between today and yesterday is a one-liner.
  * Combined with the ``S4_ALLOW_DESTRUCTIVE`` guard in ``s4_client._client()``
    and the read-only credential pattern (``S4_ENV_FILE`` priority), this
    is the closest we can get to versioning.

Output:
  ``~/Scripts/logs/s4_snapshots/YYYY-MM-DD.json.gz``
  ``~/Scripts/logs/s4_snapshots/latest.json.gz`` (symlink)

Run from cron:
  ``0 5 * * *  /opt/homebrew/bin/python3 ~/Scripts/snapshot_s4.py``

Diff against yesterday:
  ``python3 snapshot_s4.py --diff``
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

# Load creds via the same mechanism s4_client uses
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s4_client  # noqa: E402

OUT_DIR = Path.home() / "Scripts" / "logs" / "s4_snapshots"


def snapshot_bucket(studio: str) -> dict:
    """Return {key: {size, etag, mtime}} for every object in the bucket."""
    keys: dict[str, dict] = {}
    for obj in s4_client.list_objects(studio):
        keys[obj["key"]] = {
            "size": obj["size"],
            "etag": obj.get("etag", ""),
            "mtime": obj["last_modified"].isoformat() if obj.get("last_modified") else None,
        }
    return keys


def take_snapshot() -> Path:
    """Write a fresh snapshot for today. Returns the output path."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    snap = {
        "snapshot_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "buckets": {},
    }
    for studio in s4_client.STUDIO_BUCKETS:
        print(f"[{studio}] listing…", flush=True)
        keys = snapshot_bucket(studio)
        snap["buckets"][studio] = keys
        total_bytes = sum(v["size"] for v in keys.values())
        print(f"  {len(keys)} keys, {total_bytes / 1e9:.1f} GB")
    out_path = OUT_DIR / f"{date.today().isoformat()}.json.gz"
    with gzip.open(out_path, "wt") as fh:
        json.dump(snap, fh)
    # Update the `latest` symlink so diff has a stable target
    latest = OUT_DIR / "latest.json.gz"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(out_path.name)
    print(f"\nWrote {out_path}")
    return out_path


def load_snapshot(path: Path) -> dict:
    with gzip.open(path, "rt") as fh:
        return json.load(fh)


def diff_snapshots(prev: dict, curr: dict) -> dict:
    """Return {studio: {deleted: [...], added: [...], modified: [...]}}."""
    report: dict[str, dict] = {}
    for studio in sorted(set(prev["buckets"]) | set(curr["buckets"])):
        prev_keys = prev["buckets"].get(studio, {})
        curr_keys = curr["buckets"].get(studio, {})
        deleted = sorted(set(prev_keys) - set(curr_keys))
        added = sorted(set(curr_keys) - set(prev_keys))
        modified = sorted(
            k for k in (set(prev_keys) & set(curr_keys))
            if prev_keys[k]["etag"] != curr_keys[k]["etag"]
            or prev_keys[k]["size"] != curr_keys[k]["size"]
        )
        if deleted or added or modified:
            report[studio] = {
                "deleted": deleted,
                "added": added,
                "modified": modified,
            }
    return report


def find_yesterday_snapshot() -> Path | None:
    """Pick the most recent snapshot strictly before today (by filename)."""
    if not OUT_DIR.exists():
        return None
    today_str = date.today().isoformat()
    candidates = sorted(
        p for p in OUT_DIR.glob("*.json.gz")
        if not p.is_symlink() and p.stem.replace(".json", "") < today_str
    )
    return candidates[-1] if candidates else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diff", action="store_true",
                        help="Diff today vs the previous snapshot")
    parser.add_argument("--prev", type=Path, default=None,
                        help="Override: explicit path to the prior snapshot")
    parser.add_argument("--curr", type=Path, default=None,
                        help="Override: explicit path to the current snapshot")
    args = parser.parse_args()

    if args.diff:
        prev_path = args.prev or find_yesterday_snapshot()
        curr_path = args.curr or (OUT_DIR / "latest.json.gz")
        if not prev_path or not prev_path.exists():
            print("No prior snapshot to diff against.", file=sys.stderr)
            sys.exit(1)
        if not curr_path.exists():
            print("No current snapshot. Run without --diff first.", file=sys.stderr)
            sys.exit(1)
        prev = load_snapshot(prev_path)
        curr = load_snapshot(curr_path)
        report = diff_snapshots(prev, curr)
        if not report:
            print("No changes since previous snapshot.")
            return
        for studio, kinds in report.items():
            print(f"\n=== {studio} ===")
            if kinds["deleted"]:
                print(f"  DELETED ({len(kinds['deleted'])}):")
                for k in kinds["deleted"][:50]:
                    print(f"    - {k}")
                if len(kinds["deleted"]) > 50:
                    print(f"    … and {len(kinds['deleted']) - 50} more")
            if kinds["added"]:
                print(f"  ADDED ({len(kinds['added'])}):")
                for k in kinds["added"][:10]:
                    print(f"    + {k}")
                if len(kinds["added"]) > 10:
                    print(f"    … and {len(kinds['added']) - 10} more")
            if kinds["modified"]:
                print(f"  MODIFIED ({len(kinds['modified'])}):")
                for k in kinds["modified"][:10]:
                    print(f"    ~ {k}")
                if len(kinds["modified"]) > 10:
                    print(f"    … and {len(kinds['modified']) - 10} more")
        return

    take_snapshot()


if __name__ == "__main__":
    main()
