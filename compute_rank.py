#!/usr/bin/env python3
"""
compute_rank.py
===============
Scores every model across all 13 agency tabs and writes a tier to column E (Rank):

    Great | Good | Moderate | Unknown

Scoring (max 26 pts):
  SLR Views      ≥500K=3  ≥100K=2  ≥25K=1   else=0   (primary platform — subscription views)
  VRP Views      ≥1M=3    ≥500K=2  ≥100K=1  else=0   (free tube reach)
  POVR Views     ≥1M=3    ≥500K=2  ≥100K=1  else=0   (platform reach)
  OnlyFans       ≥100K=3  ≥25K=2   ≥5K=1    else=0   (strongest external demand signal)
  Twitter        ≥500K=2  ≥100K=1  else=0             (direct promo reach)
  VRP Followers  ≥2K=2    ≥500=1   else=0             (audience engagement)
  SLR Followers  ≥500=1             else=0             (SLR audience)
  SLR Scenes     ≥10=2    ≥5=1     else=0             (SLR content volume)
  Bookings       ≥5=3  ≥3=2  ≥1=1  else=0            (our booking history)
  Recency bonus  booked ≤6 months ago=2  ≤12 months=1  else=0
  AVG Rate       $1500–$2500=1  else=0                (in-demand but bookable)
  Available For  ≥12 acts=1         else=0             (versatility)
  Notes          positive=+1  negative=-2  unavailable→Unknown

Age overrides (applied after scoring):
  Age 18                          → forced Unknown (absolute no-go)
  Age 19, no bookings + no data   → forced Unknown (no verified experience)
  Age 19, <3 bookings             → capped at Good
  Age 19, ≥3 bookings            → +1 trusted return bonus, no cap

Tiers:
  Great    ≥ 9 pts
  Good      5–8 pts
  Moderate  1–4 pts
  Unknown   0 pts   (no data whatsoever)

Column E is always overwritten (no manual override preservation).

Usage:
    python3 /Users/andrewninn/Scripts/compute_rank.py
    python3 /Users/andrewninn/Scripts/compute_rank.py --tab "ATMLA"
    python3 /Users/andrewninn/Scripts/compute_rank.py --dry-run
"""

import argparse
import logging
import re
from datetime import date, datetime
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

# ── Config ─────────────────────────────────────────────────────────────────────

SPREADSHEET_ID       = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
SERVICE_ACCOUNT_FILE = Path(__file__).parent / "service_account.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADER_ROW     = 3
DATA_START_ROW = 4

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


# ── Parsers ────────────────────────────────────────────────────────────────────

def parse_shorthand(s: str) -> float:
    """'3.5M' → 3_500_000  |  '2.6K' → 2_600  |  '500' → 500  |  '' → 0"""
    if not s:
        return 0.0
    s = s.strip().replace(",", "")
    m = re.search(r"([\d.]+)\s*([KkMmBb]?)", s)
    if not m:
        return 0.0
    try:
        num = float(m.group(1))
    except ValueError:
        return 0.0
    suffix = m.group(2).upper()
    if suffix == "K":
        return num * 1_000
    if suffix == "M":
        return num * 1_000_000
    if suffix == "B":
        return num * 1_000_000_000
    return num


def parse_rate(s: str) -> int:
    """'$1,500' → 1500  |  '1500' → 1500  |  '' → 0"""
    if not s:
        return 0
    m = re.search(r"[\d,]+", s.replace("$", ""))
    if not m:
        return 0
    return int(m.group(0).replace(",", ""))


def parse_booking_count(s: str) -> int:
    """'8x · Jan 2025' → 8  |  '3x' → 3  |  '' → 0"""
    if not s:
        return 0
    m = re.match(r"(\d+)\s*x", s.strip(), re.IGNORECASE)
    return int(m.group(1)) if m else 0


def parse_booking_recency(s: str) -> int | None:
    """
    '8x · Jan 2025' → months since last booking (integer).
    Returns None if the date can't be parsed.
    """
    if not s:
        return None
    m = re.search(r"([A-Za-z]{3})\s+(\d{4})", s)
    if not m:
        return None
    try:
        last_booking = datetime.strptime(f"01 {m.group(1)} {m.group(2)}", "%d %b %Y").date()
        today = date.today()
        months = (today.year - last_booking.year) * 12 + (today.month - last_booking.month)
        return max(0, months)
    except ValueError:
        return None


def parse_age(val: str) -> int | None:
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return None


def parse_act_count(s: str) -> int:
    """Count comma-separated acts in Available For."""
    if not s:
        return 0
    return len([a for a in s.split(",") if a.strip()])


# ── Notes sentiment ────────────────────────────────────────────────────────────

# Keywords that indicate a model is currently unavailable / not bookable
UNAVAILABLE_NOTES = [
    "unavailable", "not back to shooting", "gg only", "only gg",
    "gg only", "not booking", "not shooting",
]
# Keywords that flag attitude / on-set problems — penalise score
NEGATIVE_NOTES = [
    "bad attitude", "unpredictable", "moody", "not fun to work with",
    "inability to take direction", "doesnt take direction",
    "doesn't take direction", "struggles", "gained weight",
    "not fun", "not easy",
]
# Keywords that signal a great on-set experience — small boost
POSITIVE_NOTES = [
    "loves to take direction", "great to work with", "amazing to work with",
    "can do attitude", "good actress", "fun to work with",
    "willing to", "takes direction",
]


def parse_notes_sentiment(notes: str) -> tuple[int, str]:
    """
    Scan the Notes cell for sentiment keywords.
    Returns (score_delta, label) where label is one of:
      "unavailable" → force tier to Unknown (no delta, handled separately)
      "negative"    → -2 pts
      "positive"    → +1 pt
      ""            → no signal
    """
    lower = notes.lower().strip()
    if not lower:
        return 0, ""
    for kw in UNAVAILABLE_NOTES:
        if kw in lower:
            return 0, "unavailable"
    has_negative = any(kw in lower for kw in NEGATIVE_NOTES)
    has_positive = any(kw in lower for kw in POSITIVE_NOTES)
    if has_negative:
        return -2, "negative"
    if has_positive:
        return 1, "positive"
    return 0, ""


# ── Scoring ────────────────────────────────────────────────────────────────────

def score_model(row: dict) -> tuple[int, str, dict]:
    """
    Compute a weighted score and return (score, tier, breakdown).
    `row` is a dict mapping column header → cell value.
    Age overrides are applied after base scoring.
    """
    b = {}  # breakdown: component → points earned

    # ── Platform reach: SLR Views  (max 3) — primary platform ───────────────
    slr_views = parse_shorthand(row.get("SLR Views", ""))
    b["slr_v"] = 3 if slr_views >= 500_000 else 2 if slr_views >= 100_000 else 1 if slr_views >= 25_000 else 0

    # ── Platform reach: VRP Views  (max 3) ──────────────────────────────────
    vrp_views = parse_shorthand(row.get("VRP Views", ""))
    b["vrp_v"] = 3 if vrp_views >= 1_000_000 else 2 if vrp_views >= 500_000 else 1 if vrp_views >= 100_000 else 0

    # ── Platform reach: POVR Views  (max 3) ─────────────────────────────────
    povr_views = parse_shorthand(row.get("POVR Views", ""))
    b["povr_v"] = 3 if povr_views >= 1_000_000 else 2 if povr_views >= 500_000 else 1 if povr_views >= 100_000 else 0

    # ── OnlyFans subscribers  (max 3) — strongest external demand signal ─────
    of_subs = parse_shorthand(row.get("OnlyFans", ""))
    b["of"] = 3 if of_subs >= 100_000 else 2 if of_subs >= 25_000 else 1 if of_subs >= 5_000 else 0

    # ── Twitter/X followers  (max 2) ─────────────────────────────────────────
    tw_fol = parse_shorthand(row.get("Twitter", ""))
    b["tw"] = 2 if tw_fol >= 500_000 else 1 if tw_fol >= 100_000 else 0

    # ── Audience engagement: VRP Followers  (max 2) ──────────────────────────
    vrp_fol = parse_shorthand(row.get("VRP Followers", ""))
    b["vrp_f"] = 2 if vrp_fol >= 2_000 else 1 if vrp_fol >= 500 else 0

    # ── Audience engagement: SLR Followers  (max 1) ──────────────────────────
    slr_fol = parse_shorthand(row.get("SLR Followers", ""))
    b["slr_f"] = 1 if slr_fol >= 500 else 0

    # ── SLR content volume: SLR Scenes  (max 2) ──────────────────────────────
    slr_scenes = parse_shorthand(row.get("SLR Scenes", ""))
    b["slr_s"] = 2 if slr_scenes >= 10 else 1 if slr_scenes >= 5 else 0

    # ── Our booking count  (max 3) ────────────────────────────────────────────
    # "Bookings" column holds an integer; fall back to old "Dates Booked" format
    bookings_raw = row.get("Bookings", "").strip()
    try:
        bookings = int(float(bookings_raw)) if bookings_raw else 0
    except (ValueError, TypeError):
        bookings = parse_booking_count(row.get("Dates Booked", ""))
    b["book"] = 3 if bookings >= 5 else 2 if bookings >= 3 else 1 if bookings >= 1 else 0

    # ── Booking recency bonus  (max 2) ───────────────────────────────────────
    # "Last Booked Date" column holds "Mon YYYY" text; fall back to old column name
    lbd_raw = row.get("Last Booked Date", "") or row.get("Dates Booked", "")
    months_ago = parse_booking_recency(lbd_raw)
    if months_ago is not None:
        b["recency"] = 2 if months_ago <= 6 else 1 if months_ago <= 12 else 0
    else:
        b["recency"] = 0

    # ── AVG Rate: in-demand but bookable  (max 1) ─────────────────────────────
    # >$2500 = premium/selective — desirable but costly for routine bookings
    rate = parse_rate(row.get("AVG Rate", ""))
    b["rate"] = 1 if 1_500 <= rate <= 2_500 else 0

    # ── Available For breadth  (max 1) ────────────────────────────────────────
    act_count = parse_act_count(row.get("Available For", ""))
    b["avail"] = 1 if act_count >= 12 else 0

    # ── Notes sentiment  (max +1, min -2) ────────────────────────────────────
    notes_delta, notes_label = parse_notes_sentiment(row.get("Notes", ""))
    b["notes"] = notes_delta if notes_label != "unavailable" else 0

    # ── Age: trusted return bonus ─────────────────────────────────────────────
    b["age_bonus"] = 0  # may be set below

    pts = max(0, sum(b.values()))  # clamp to 0 — can't go negative

    # ── Base tier ────────────────────────────────────────────────────────────
    if pts >= 9:     tier = "Great"
    elif pts >= 5:   tier = "Good"
    elif pts >= 1:   tier = "Moderate"
    else:            tier = "Unknown"

    # ── Age overrides ────────────────────────────────────────────────────────
    age = parse_age(row.get("Age", ""))
    if age is not None and age < 20:
        has_platform = bool(
            row.get("SLR Views", "").strip() or
            row.get("SLR Followers", "").strip() or
            row.get("SLR Scenes", "").strip() or
            row.get("VRP Views", "").strip() or
            row.get("POVR Views", "").strip()
        )
        has_bookings = bookings > 0

        if age == 18:
            tier = "Unknown"
        elif age == 19:
            if not has_bookings and not has_platform:
                tier = "Unknown"
            elif bookings >= 3:
                # Trusted return talent — +1 bonus, no cap
                b["age_bonus"] = 1
                pts += 1
                if pts >= 9:   tier = "Great"
                elif pts >= 5: tier = "Good"
                elif pts >= 1: tier = "Moderate"
            else:
                # Cap at Good
                if tier == "Great":
                    tier = "Good"

    # ── Availability override (notes) ─────────────────────────────────────────
    if notes_label == "unavailable":
        tier = "Unknown"

    return pts, tier, b


# ── Sheet helpers ──────────────────────────────────────────────────────────────

def col_index_to_a1(idx: int) -> str:
    result = ""
    n = idx + 1
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def fmt_breakdown(b: dict) -> str:
    """Format score breakdown as a compact inline string, omitting zeros."""
    labels = {
        "slr_v":    "slr",
        "vrp_v":    "vrp",
        "povr_v":   "povr",
        "of":       "of",
        "tw":       "tw",
        "vrp_f":    "vrp_fol",
        "slr_f":    "slr_fol",
        "slr_s":    "slr_scenes",
        "book":     "booked",
        "recency":  "recency",
        "rate":     "rate",
        "avail":    "avail",
        "notes":    "notes",
        "age_bonus":"age_bonus",
    }
    parts = [f"{labels[k]}={v}" for k, v in b.items() if v]
    return "  [" + "  ".join(parts) + "]" if parts else ""


# ── Tab processor ──────────────────────────────────────────────────────────────

def process_tab(ws, dry_run: bool) -> tuple[int, dict]:
    all_rows = ws.get_all_values()
    if len(all_rows) < HEADER_ROW:
        return 0, {}

    headers = [h.strip() for h in all_rows[HEADER_ROW - 1]]
    if not headers or not headers[0]:
        return 0, {}

    col_map  = {h: i for i, h in enumerate(headers) if h}
    name_col = col_map.get("Name", 0)
    rank_col = col_map.get("Rank")

    if rank_col is None:
        log.warning(f"  No 'Rank' column found — skipping")
        return 0, {}

    rank_a1     = col_index_to_a1(rank_col)
    updates     = []
    tier_counts = {"Great": 0, "Good": 0, "Moderate": 0, "Unknown": 0}

    for row_i, row in enumerate(all_rows[DATA_START_ROW - 1:], start=DATA_START_ROW):
        if len(row) <= name_col:
            continue
        name = row[name_col].strip()
        if not name:
            continue

        row_dict = {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
        pts, tier, breakdown = score_model(row_dict)
        tier_counts[tier] += 1

        log.info(f"    {name}: {pts}pts → {tier}{fmt_breakdown(breakdown)}")

        updates.append({
            "range":  f"'{ws.title}'!{rank_a1}{row_i}",
            "values": [[tier]],
        })

    if updates and not dry_run:
        ws.spreadsheet.values_batch_update({
            "valueInputOption": "RAW",
            "data": updates,
        })

    return len(updates), tier_counts


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Auto-score models into Great/Good/Moderate/Unknown")
    parser.add_argument("--tab",     help="Process only this tab")
    parser.add_argument("--dry-run", action="store_true", help="Score but don't write to sheet")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("Compute Model Ranks")
    log.info("=" * 60)
    log.info("")
    log.info("Scoring rubric (max 26 pts):")
    log.info("  SLR Views:      ≥500K=3  ≥100K=2  ≥25K=1  (subscription platform — calibrated lower thresholds)")
    log.info("  VRP Views:      ≥1M=3  ≥500K=2  ≥100K=1")
    log.info("  POVR Views:     ≥1M=3  ≥500K=2  ≥100K=1")
    log.info("  OnlyFans:       ≥100K=3  ≥25K=2  ≥5K=1   (strongest external demand signal)")
    log.info("  Twitter:        ≥500K=2  ≥100K=1")
    log.info("  VRP Followers:  ≥2K=2  ≥500=1")
    log.info("  SLR Followers:  ≥500=1")
    log.info("  SLR Scenes:     ≥10=2  ≥5=1")
    log.info("  Bookings:       ≥5=3  ≥3=2  ≥1=1")
    log.info("  Recency bonus:  ≤6mo=2  ≤12mo=1")
    log.info("  AVG Rate:       $1500–$2500=1  (>$2500 = too premium, no pts)")
    log.info("  Available For:  ≥12 acts=1  (versatility)")
    log.info("  Notes:          positive=+1  negative=-2  unavailable→Unknown")
    log.info("  Great≥9  Good≥5  Moderate≥1  Unknown=0")
    log.info("  Age 18 → Unknown  |  Age 19 no data → Unknown")
    log.info("  Age 19 <3 bookings → cap Good  |  Age 19 ≥3 bookings → +1 bonus, no cap")
    log.info("")

    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc    = gspread.authorize(creds)
    ss    = gc.open_by_key(SPREADSHEET_ID)

    total_written = 0
    grand_totals  = {"Great": 0, "Good": 0, "Moderate": 0, "Unknown": 0}

    for ws in ss.worksheets():
        if args.tab and ws.title != args.tab:
            continue

        log.info(f"[{ws.title}]")
        n, counts = process_tab(ws, args.dry_run)
        total_written += n

        if n:
            parts = "  ".join(f"{t}: {counts[t]}" for t in ("Great", "Good", "Moderate", "Unknown") if counts[t])
            log.info(f"  → {n} rows ranked  ({parts})")
            for t, c in counts.items():
                grand_totals[t] += c
        else:
            log.info(f"  → Nothing to update (all ranked or no data)")

    log.info("")
    log.info("=" * 60)
    log.info(f"Done. {total_written} cells written.")
    if total_written:
        log.info(f"  Great:    {grand_totals['Great']}")
        log.info(f"  Good:     {grand_totals['Good']}")
        log.info(f"  Moderate: {grand_totals['Moderate']}")
        log.info(f"  Unknown:  {grand_totals['Unknown']}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
