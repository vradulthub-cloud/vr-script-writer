"""
Pull every human-written script row from the Scripts Sheet into JSONL.

The output is the source of truth for training data. Every row that has
non-empty plot text is treated as a positive example — these are scripts
that humans wrote, reviewed, or shipped.

Output schema (one JSON object per line):
  {
    "source_tab":   "January 2026",
    "source_row":   12,
    "studio":       "VRHush",
    "scene_type":   "BG",
    "female":       "Sophia Locke",
    "male":         "POV",
    "shoot_date":   "2026-01-14",
    "location":     "Bedroom 1",
    "title":        "Late-Night Confession",
    "theme":        "Late-Night Confession",
    "plot":         "...",
    "wardrobe_f":   "...",
    "wardrobe_m":   "...",
    "props":        "...",
    "status":       "approved",
    "input":        "Studio: VRHush\\nScene Type: BG\\nFemale: Sophia Locke\\nMale: POV",
    "output":       "THEME: ...\\nPLOT: ...\\nSHOOT LOCATION: ...\\n..."
  }

The `input` / `output` strings are pre-formatted prompt/completion pairs
ready for instruction-tuning frameworks (Unsloth, Axolotl, etc.) — but
the raw fields are kept so we can re-format later without re-pulling.

Usage:
    python training/extract_scripts.py [--service-account PATH] [--out PATH]

Defaults:
    --service-account  ~/Scripts/service_account.json
    --out              training/data/scripts_dataset.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from calendar import month_name
from collections import Counter, defaultdict
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials


SCRIPTS_SHEET_ID = "1cY-8zNHLmD-oWdyEa2Mt3VY3nsFXHLEeZx0n42uf3ZQ"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Sheet column layout (0-indexed):
COL_DATE       = 0
COL_STUDIO     = 1
COL_LOCATION   = 2
COL_SCENE_TYPE = 3
COL_FEMALE     = 4
COL_MALE       = 5
COL_THEME      = 6
COL_WARDROBE_F = 7
COL_WARDROBE_M = 8
COL_PLOT       = 9
COL_TITLE      = 10
COL_PROPS      = 11
COL_STATUS     = 12

MONTH_TAB_RE = re.compile(
    r"^(" + "|".join(month_name[1:]) + r")\s+\d{4}$",
    re.IGNORECASE,
)

# Sheet drift — normalize common typos and inconsistent casings to a single
# canonical value before they pollute the training set. Keep this list small;
# add only what we actually see in the data.
STUDIO_ALIASES = {
    "fuckpassvr": "FuckPassVR",
    "vrhush":     "VRHush",
    "vrallure":   "VRAllure",
    "naughtyjoi": "NaughtyJOI",
}

SCENE_TYPE_ALIASES = {
    "bg-cp": "BGCP",
    "bg_cp": "BGCP",
    "bg cp": "BGCP",
    "cp":    "BGCP",
    "":      "BG",   # default empty cells to BG
}

VRA_SCENE_TYPE_OVERRIDE = "SOLO"   # VRAllure is always SOLO regardless of sheet


def normalize_studio(raw: str) -> str:
    """Lookup canonical studio name; fall back to the raw value."""
    return STUDIO_ALIASES.get(raw.strip().lower(), raw.strip())


def normalize_scene_type(raw: str, studio: str) -> str:
    """Normalize scene_type and override VRAllure → SOLO."""
    if studio == "VRAllure":
        return VRA_SCENE_TYPE_OVERRIDE
    key = raw.strip().lower()
    if key in SCENE_TYPE_ALIASES:
        return SCENE_TYPE_ALIASES[key]
    return raw.strip().upper()


def get_client(service_account_path: Path) -> gspread.Client:
    creds = Credentials.from_service_account_file(str(service_account_path), scopes=SCOPES)
    return gspread.authorize(creds)


def format_input(studio: str, scene_type: str, female: str, male: str) -> str:
    """Build the prompt-side string for instruction-tuning."""
    parts = [
        f"Studio: {studio}",
        f"Scene Type: {scene_type or 'BG'}",
        f"Female Talent: {female}",
    ]
    # VRAllure has no male performer on set (torso doll only).
    if studio != "VRAllure":
        parts.append(f"Male Talent: {male or 'POV'}")
    return "\n".join(parts)


def format_output(
    *, studio: str, theme: str, plot: str, location: str,
    props: str, wardrobe_f: str, wardrobe_m: str,
) -> str:
    """Build the completion-side string in the canonical script schema."""
    sections = [
        ("THEME", theme),
        ("PLOT", plot),
        ("SHOOT LOCATION", location),
        ("PROPS", props),
        ("WARDROBE - FEMALE", wardrobe_f),
    ]
    # VRAllure scripts omit WARDROBE - MALE (no male on set).
    if studio != "VRAllure":
        sections.append(("WARDROBE - MALE", wardrobe_m))
    return "\n\n".join(f"{label}: {value}" for label, value in sections if value)


def is_usable_row(plot: str, theme: str, female: str) -> bool:
    """A script is training-worthy if it has at least a plot, theme, and a female lead."""
    return bool(plot.strip() and theme.strip() and female.strip())


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--service-account",
        type=Path,
        default=Path.home() / "Scripts" / "service_account.json",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).parent / "data" / "scripts_dataset.jsonl",
    )
    args = p.parse_args()

    if not args.service_account.exists():
        print(f"ERROR: service account file not found at {args.service_account}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)

    print(f"Connecting with {args.service_account}...")
    client = get_client(args.service_account)
    sh = client.open_by_key(SCRIPTS_SHEET_ID)

    all_titles = [ws.title for ws in sh.worksheets()]
    month_tabs = [t for t in all_titles if MONTH_TAB_RE.match(t)]
    print(f"Found {len(month_tabs)} monthly tabs out of {len(all_titles)} total tabs.")

    per_studio = Counter()
    per_scene_type = Counter()
    per_studio_scene = defaultdict(Counter)
    skipped = Counter()
    total_written = 0

    with args.out.open("w", encoding="utf-8") as fh:
        for tab_name in month_tabs:
            try:
                ws = sh.worksheet(tab_name)
                rows = ws.get_all_values()[1:]  # skip header
            except Exception as exc:
                print(f"  ! {tab_name}: read failed — {exc}", file=sys.stderr)
                continue

            tab_count = 0
            for row_idx, row in enumerate(rows, start=2):  # row 2 = first data row
                padded = row + [""] * (13 - len(row))
                studio       = normalize_studio(padded[COL_STUDIO])
                scene_type   = normalize_scene_type(padded[COL_SCENE_TYPE], studio)
                female       = padded[COL_FEMALE].strip()
                male         = padded[COL_MALE].strip() or "POV"
                shoot_date   = padded[COL_DATE].strip()
                location     = padded[COL_LOCATION].strip()
                title        = padded[COL_TITLE].strip()
                theme        = padded[COL_THEME].strip()
                plot         = padded[COL_PLOT].strip()
                wardrobe_f   = padded[COL_WARDROBE_F].strip()
                wardrobe_m   = padded[COL_WARDROBE_M].strip()
                props        = padded[COL_PROPS].strip()
                status       = padded[COL_STATUS].strip()

                if not studio:
                    skipped["empty_studio"] += 1
                    continue
                if not is_usable_row(plot, theme, female):
                    skipped["incomplete"] += 1
                    continue

                record = {
                    "source_tab":   tab_name,
                    "source_row":   row_idx,
                    "studio":       studio,
                    "scene_type":   scene_type,
                    "female":       female,
                    "male":         male,
                    "shoot_date":   shoot_date,
                    "location":     location,
                    "title":        title,
                    "theme":        theme,
                    "plot":         plot,
                    "wardrobe_f":   wardrobe_f,
                    "wardrobe_m":   wardrobe_m,
                    "props":        props,
                    "status":       status,
                    "input":  format_input(studio, scene_type, female, male),
                    "output": format_output(
                        studio=studio,
                        theme=theme, plot=plot, location=location,
                        props=props, wardrobe_f=wardrobe_f, wardrobe_m=wardrobe_m,
                    ),
                }
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_written += 1
                tab_count += 1

                per_studio[studio] += 1
                per_scene_type[scene_type] += 1
                per_studio_scene[studio][scene_type] += 1

            print(f"  • {tab_name}: {tab_count} rows kept (of {len(rows)})")

    print(f"\nWrote {total_written} rows to {args.out}")
    print("\n--- Per studio ---")
    for studio, count in per_studio.most_common():
        breakdown = ", ".join(f"{st}={n}" for st, n in per_studio_scene[studio].most_common())
        print(f"  {studio:20s}  {count:4d}   ({breakdown})")
    print("\n--- Per scene type ---")
    for st, count in per_scene_type.most_common():
        print(f"  {st:6s}  {count}")
    if skipped:
        print("\n--- Skipped ---")
        for reason, count in skipped.most_common():
            print(f"  {reason:20s}  {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
