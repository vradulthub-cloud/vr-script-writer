#!/usr/bin/env python3
"""
daily_grail_update.py
=====================
Checks the 2026 Scripts sheet for scenes shooting today and appends
new rows (with the next sequential studio ID) to The Grail – Metadata Master.

Each new row includes auto-generated Category and Tags derived from performer
attributes (sourced from the Grail's own history and the Model Booking List).
FPVR rows also include the four Destination location columns.

Usage:
    python3 daily_grail_update.py              # live run
    python3 daily_grail_update.py --dry-run    # preview only, no writes
"""

import argparse
import logging
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

# ── Configuration ─────────────────────────────────────────────────────────────
SCRIPTS_SHEET_ID = "1bM1G49p2KK9WY3WfjzPixrWUw8KBiDGKR-0jKw5QUVc"
GRAIL_SHEET_ID   = "1Eq5G5FU6A8EqeFZCnZjrEaMYS8F1DiK5vP5tCSINeJk"
BOOKING_SHEET_ID = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
SA_CREDENTIALS   = Path("/Users/andrewninn/Scripts/service_account.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Studio name (Script col B) → (Grail tab, site code, rows per shoot)
# NaughtyJOI always produces 2 rows: Nice (lower ID) then Naughty (higher ID)
STUDIO_MAP: dict[str, tuple[str, str, int]] = {
    "FuckPassVR":  ("FPVR",  "fpvr", 1),
    "FuckpassVR":  ("FPVR",  "fpvr", 1),   # handle inconsistent capitalisation
    "VRHush":      ("VRH",   "vrh",  1),
    "VRAllure":    ("VRA",   "vra",  1),
    "NaughtyJOI":  ("NNJOI", "njoi", 2),
}

# Column alignment per Grail tab
# FPVR writes A–K (11 cols); all others write A–G (7 cols)
TAB_COL_ALIGN: dict[str, list[str]] = {
    "FPVR":  ["CENTER", "CENTER", "CENTER", "LEFT", "LEFT", "LEFT", "LEFT",
              "CENTER", "CENTER", "CENTER", "CENTER"],
    "VRH":   ["CENTER", "CENTER", "RIGHT",  "LEFT", "LEFT", "LEFT", "LEFT"],
    "VRA":   ["CENTER", "CENTER", "RIGHT",  "LEFT", "LEFT", "LEFT", "LEFT"],
    "NNJOI": ["CENTER", "CENTER", "CENTER", "LEFT", "LEFT", "LEFT", "LEFT"],
}

ALL_COL_LETTERS = list("ABCDEFGHIJK")   # index 0 = A … 10 = K

# ── 2026 Scripts column indices (0-based) ─────────────────────────────────────
COL_DATE        = 0   # A
COL_STUDIO      = 1   # B
COL_DESTINATION = 2   # C
COL_TYPE        = 3   # D  (BG / BGCP / Solo / JOI …)
COL_FEMALE      = 4   # E
COL_MALE        = 5   # F
COL_THEME       = 6   # G
COL_PLOT        = 9   # J
COL_TITLE       = 10  # K

# ── Performer attribute vocabulary ────────────────────────────────────────────
HAIR_COLORS          = {"Brunette", "Blonde", "Redhead"}
ETHNICITIES_CAT      = {"Latina", "Asian", "Ebony"}
TIT_CATS             = {"Natural Tits", "Big Tits", "Small Tits"}
BODY_EXTRAS          = {"Big Ass", "Milf", "Petite", "Curvy", "Hairy Pussy"}
PERFORMER_EXTRA_TAGS = {"Fake Tits", "Tattoos", "Stockings", "Glasses", "Pierced Nipples"}

# Booking sheet tabs that contain performer rows
BOOKING_AGENCY_TABS = [
    "OC Models", "Invision Models", "Hussie Models", "The Bakery Talent",
    "East Coast Talent", "The Model Service", "ATMLA", "Coxxx Models",
    "101 Models", "Zen Models", "Speigler", "Foxxx Modeling", "Nexxxt Level",
]

# Booking-sheet hair value → Grail category term
HAIR_MAP: dict[str, str] = {
    "brown":      "Brunette",
    "black":      "Brunette",   # may be overridden by ethnicity data from Grail
    "dark":       "Brunette",
    "brunette":   "Brunette",
    "blonde":     "Blonde",
    "sandy":      "Blonde",
    "strawberry": "Blonde",
    "red":        "Redhead",
    "auburn":     "Redhead",
}

# ── US State abbreviations → full names ───────────────────────────────────────
US_STATES: dict[str, str] = {
    "AL": "Alabama",        "AK": "Alaska",         "AZ": "Arizona",
    "AR": "Arkansas",       "CA": "California",     "CO": "Colorado",
    "CT": "Connecticut",    "DE": "Delaware",        "FL": "Florida",
    "GA": "Georgia",        "HI": "Hawaii",          "ID": "Idaho",
    "IL": "Illinois",       "IN": "Indiana",         "IA": "Iowa",
    "KS": "Kansas",         "KY": "Kentucky",        "LA": "Louisiana",
    "ME": "Maine",          "MD": "Maryland",        "MA": "Massachusetts",
    "MI": "Michigan",       "MN": "Minnesota",       "MS": "Mississippi",
    "MO": "Missouri",       "MT": "Montana",         "NE": "Nebraska",
    "NV": "Nevada",         "NH": "New Hampshire",   "NJ": "New Jersey",
    "NM": "New Mexico",     "NY": "New York",        "NC": "North Carolina",
    "ND": "North Dakota",   "OH": "Ohio",            "OK": "Oklahoma",
    "OR": "Oregon",         "PA": "Pennsylvania",    "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota",    "TN": "Tennessee",
    "TX": "Texas",          "UT": "Utah",            "VT": "Vermont",
    "VA": "Virginia",       "WA": "Washington",      "WV": "West Virginia",
    "WI": "Wisconsin",      "WY": "Wyoming",         "DC": "District of Columbia",
}

# Known international FPVR shoot locations: "City, CC" → (continent, country, region, city)
INTL_LOCATIONS: dict[str, tuple[str, str, str, str]] = {
    # Brazil
    "Salvador, BR":          ("South America", "Brazil", "Bahia", "Salvador"),
    "Rio de Janeiro, BR":    ("South America", "Brazil", "Rio de Janeiro", "Rio de Janeiro"),
    "Sao Paulo, BR":         ("South America", "Brazil", "São Paulo", "São Paulo"),
    "São Paulo, BR":         ("South America", "Brazil", "São Paulo", "São Paulo"),
    "Florianopolis, BR":     ("South America", "Brazil", "Santa Catarina", "Florianópolis"),
    # Belize
    "Placencia, BZ":         ("North America", "Belize", "Stann Creek District", "Placencia"),
    "Belize City, BZ":       ("North America", "Belize", "Belize District", "Belize City"),
    # Mexico
    "Cancun, MX":            ("North America", "Mexico", "Quintana Roo", "Cancún"),
    "Mexico City, MX":       ("North America", "Mexico", "Mexico City", "Mexico City"),
    "Playa del Carmen, MX":  ("North America", "Mexico", "Quintana Roo", "Playa del Carmen"),
    # Dominican Republic
    "Punta Cana, DO":        ("North America", "Dominican Republic", "La Altagracia", "Punta Cana"),
    "Santo Domingo, DO":     ("North America", "Dominican Republic", "Distrito Nacional", "Santo Domingo"),
    # Colombia
    "Cartagena, CO":         ("South America", "Colombia", "Bolívar", "Cartagena"),
    "Medellin, CO":          ("South America", "Colombia", "Antioquia", "Medellín"),
    # Czech Republic
    "Prague, CZ":            ("Europe", "Czech Republic", "Prague", "Prague"),
    "Brno, CZ":              ("Europe", "Czech Republic", "South Moravian", "Brno"),
    "Ostrava, CZ":           ("Europe", "Czech Republic", "Moravian-Silesian", "Ostrava"),
    # Spain
    "Madrid, ES":            ("Europe", "Spain", "Comunidad de Madrid", "Madrid"),
    "Barcelona, ES":         ("Europe", "Spain", "Catalonia", "Barcelona"),
    "Ibiza, ES":             ("Europe", "Spain", "Balearic Islands", "Ibiza"),
    # Italy
    "Rome, IT":              ("Europe", "Italy", "Lazio", "Rome"),
    "Milan, IT":             ("Europe", "Italy", "Lombardy", "Milan"),
    "Venice, IT":            ("Europe", "Italy", "Veneto", "Venice"),
    "Florence, IT":          ("Europe", "Italy", "Tuscany", "Florence"),
    # UK
    "London, UK":            ("Europe", "United Kingdom", "England", "London"),
    "London, GB":            ("Europe", "United Kingdom", "England", "London"),
    # Hungary
    "Budapest, HU":          ("Europe", "Hungary", "Budapest", "Budapest"),
    # Portugal
    "Lisbon, PT":            ("Europe", "Portugal", "Lisbon", "Lisbon"),
    "Porto, PT":             ("Europe", "Portugal", "Porto", "Porto"),
    # France
    "Paris, FR":             ("Europe", "France", "Île-de-France", "Paris"),
    # Germany
    "Berlin, DE":            ("Europe", "Germany", "Berlin", "Berlin"),
    # Netherlands
    "Amsterdam, NL":         ("Europe", "Netherlands", "North Holland", "Amsterdam"),
    # Caribbean
    "San Juan, PR":          ("North America", "Puerto Rico", "San Juan", "San Juan"),
    "Nassau, BS":            ("North America", "Bahamas", "New Providence", "Nassau"),
    "Montego Bay, JM":       ("North America", "Jamaica", "St. James", "Montego Bay"),
    # Asia
    "Bangkok, TH":           ("Asia", "Thailand", "Bangkok", "Bangkok"),
    "Bali, ID":              ("Asia", "Indonesia", "Bali", "Denpasar"),
    "Tokyo, JP":             ("Asia", "Japan", "Tokyo", "Tokyo"),
}

TODAY          = date.today()
TODAY_DISPLAY  = TODAY.strftime("%Y-%m-%d")
MONTH_TAB_NAME = TODAY.strftime("%B %Y")

LOG_DIR = Path("/Users/andrewninn/Scripts/logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / f"daily_grail_{TODAY_DISPLAY}.log"),
    ],
)
log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_client() -> gspread.Client:
    creds = Credentials.from_service_account_file(str(SA_CREDENTIALS), scopes=SCOPES)
    return gspread.authorize(creds)


def _retry(func, retries: int = 4, base_sleep: float = 12.0):
    """Retry a gspread API call on 429 rate-limit errors with exponential back-off."""
    for attempt in range(retries):
        try:
            return func()
        except gspread.exceptions.APIError as exc:
            if "429" in str(exc) and attempt < retries - 1:
                wait = base_sleep * (2 ** attempt)
                log.warning(f"Rate limited (429) – waiting {wait:.0f}s …")
                time.sleep(wait)
            else:
                raise


def _parse_date_cell(cell: str) -> date | None:
    """Parse M/D/YY or MM/DD/YY date strings; return None on failure."""
    from datetime import datetime
    for fmt in ("%m/%d/%y", "%-m/%-d/%y"):
        try:
            return datetime.strptime(cell.strip(), fmt).date()
        except ValueError:
            pass
    try:
        parts = cell.strip().split("/")
        if len(parts) == 3:
            m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
            y += 2000 if y < 100 else 0
            return date(y, m, d)
    except (ValueError, IndexError):
        pass
    return None


def _tab_stats(ws: gspread.Worksheet) -> dict:
    """Return {maxId, dupes} for a Grail tab by scanning column B (index 1)."""
    rows = _retry(ws.get_all_values)
    ids: list[int] = []
    for row in rows[1:]:
        if len(row) > 1 and row[1].strip():
            try:
                ids.append(int(row[1]))
            except ValueError:
                pass
    if not ids:
        return {"maxId": 0, "dupes": []}
    counts: dict[int, int] = {}
    for n in ids:
        counts[n] = counts.get(n, 0) + 1
    dupes = [f"ID {n} ×{c}" for n, c in sorted(counts.items()) if c > 1]
    return {"maxId": max(ids), "dupes": dupes}


# ── Performer attribute extraction ────────────────────────────────────────────

def _extract_grail_attrs(category: str, tags: str) -> dict:
    """Parse category/tag strings from an existing Grail row into an attrs dict."""
    cat_tokens = [t.strip() for t in category.split(",")]
    tag_tokens  = [t.strip() for t in tags.split(",")]
    cat_set = set(cat_tokens)
    tag_set  = set(tag_tokens)

    # Hair (special-case "Black Hair" = Asian with non-standard hair entry)
    hair = next((t for t in cat_tokens if t in HAIR_COLORS), None)
    if not hair and "Black Hair" in cat_set:
        hair = "Black Hair"
    if not hair:
        return {}

    return {
        "hair":       hair,
        "ethnicity":  [t for t in ETHNICITIES_CAT if t in cat_set],
        "tit_cats":   [t for t in TIT_CATS if t in cat_set],
        "body_extras":[t for t in BODY_EXTRAS if t in cat_set],
        "fake_tits":  "Fake Tits" in tag_set,
        "extra_tags": [t for t in PERFORMER_EXTRA_TAGS if t in tag_set],
    }


def _parse_cup_size(measurements: str) -> str | None:
    """Return cup-size letter(s) from a measurements string, or None."""
    m = re.search(r'\d{2,3}\s*([A-G]+)', measurements, re.IGNORECASE)
    return m.group(1).upper() if m else None


def _determine_tit_cats(cup: str | None, natural: bool,
                         avail_for: str = "") -> list[str]:
    """Infer tit-category tokens from cup size, natural flag, and Available For."""
    if not natural:
        return ["Big Tits"]   # fake = always Big Tits

    if cup:
        c = cup.upper()
        if c in ("A", "B"):
            return ["Small Tits"]
        if c == "C":
            return ["Natural Tits"]
        return ["Big Tits", "Natural Tits"]   # D / DD / DDD / E / F / G

    # No cup letter — fall back on Available For hints
    avail_lower = avail_for.lower()
    if "big boobs" in avail_lower or "big tits" in avail_lower:
        return ["Big Tits", "Natural Tits"]

    return ["Natural Tits"]


def _extract_booking_attrs(row: list) -> dict:
    """Extract performer attributes from a booking-sheet data row."""
    if len(row) < 15:
        return {}

    age_str      = row[1].strip()  if len(row) > 1  else ""
    avail_for    = row[8].strip()  if len(row) > 8  else ""
    measurements = row[13].strip() if len(row) > 13 else ""
    hair_raw     = row[14].strip().lower() if len(row) > 14 else ""
    natural_raw  = row[16].strip().lower() if len(row) > 16 else ""
    tattoos_raw  = row[17].strip() if len(row) > 17 else ""

    if not hair_raw:
        return {}

    hair = next((v for k, v in HAIR_MAP.items() if k in hair_raw), None)
    if not hair:
        return {}

    natural    = natural_raw == "yes"
    cup        = _parse_cup_size(measurements)
    tit_cats   = _determine_tit_cats(cup, natural, avail_for)

    # Milf: age ≥ 35
    body_extras: list[str] = []
    try:
        if int(age_str) >= 35:
            body_extras.append("Milf")
    except (ValueError, TypeError):
        pass

    # Big Ass from Available For
    avail_lower = avail_for.lower()
    if "big butt" in avail_lower or "big ass" in avail_lower:
        body_extras.append("Big Ass")

    # Tattoos
    extra_tags: list[str] = []
    if tattoos_raw and tattoos_raw.lower() not in ("no", "none", ""):
        extra_tags.append("Tattoos")

    return {
        "hair":        hair,
        "ethnicity":   [],   # booking sheet has no ethnicity field
        "tit_cats":    tit_cats,
        "body_extras": body_extras,
        "fake_tits":   not natural,
        "extra_tags":  extra_tags,
    }


# ── Performer lookup ──────────────────────────────────────────────────────────

def build_performer_lookup(
    grail_sh: gspread.Spreadsheet,
    booking_sh: gspread.Spreadsheet,
) -> dict[str, dict]:
    """
    Build a {performer_name: attrs_dict} lookup.

    Primary source: existing Grail rows with filled categories (most accurate).
    Fallback:       Model Booking List for performers with no Grail history.
    """
    lookup: dict[str, dict] = {}

    # ── 1. Grail history ──────────────────────────────────────────────────
    for tab in ["FPVR", "VRH", "VRA", "NNJOI"]:
        try:
            ws = grail_sh.worksheet(tab)
            rows = _retry(ws.get_all_values)
            for row in rows[1:]:
                if len(row) <= 6 or not row[5].strip():
                    continue
                if not (row[1].strip().isdigit() and row[4].strip()):
                    continue

                attrs = _extract_grail_attrs(row[5], row[6] if len(row) > 6 else "")
                if not attrs:
                    continue

                # Split performers; skip compilation rows (>2 names)
                performers = [
                    p.strip() for p in row[4].split(",")
                    if p.strip() and p.strip() != "VariousHostess"
                ]
                if 1 <= len(performers) <= 2:
                    # Female is always first; overwrite with most-recent entry
                    lookup[performers[0]] = attrs

            time.sleep(0.5)
        except Exception as exc:
            log.warning(f"  Grail tab '{tab}' skipped during lookup build: {exc}")

    log.info(f"  Grail history: {len(lookup)} performer(s) loaded")

    # ── 2. Booking List fallback ──────────────────────────────────────────
    new_from_booking = 0
    for tab_name in BOOKING_AGENCY_TABS:
        try:
            ws = booking_sh.worksheet(tab_name)
            rows = _retry(ws.get_all_values)
            # Row 0 = agency name, Row 1 = website, Row 2 = header, Row 3+ = data
            for row in rows[3:]:
                name = row[0].strip() if row else ""
                if not name or name in lookup:
                    continue
                attrs = _extract_booking_attrs(row)
                if attrs:
                    lookup[name] = attrs
                    new_from_booking += 1
            time.sleep(0.3)
        except Exception as exc:
            log.warning(f"  Booking tab '{tab_name}' skipped: {exc}")

    log.info(f"  Booking List added: {new_from_booking} new performer(s)")
    return lookup


# ── Category / Tag builders per studio ────────────────────────────────────────

def _build_fpvr_cat_tags(attrs: dict, scene_type: str) -> tuple[str, str]:
    hair        = attrs.get("hair", "")
    ethnicity   = attrs.get("ethnicity", [])
    tit_cats    = attrs.get("tit_cats", [])
    body_extras = attrs.get("body_extras", [])
    fake_tits   = attrs.get("fake_tits", False)
    extra_tags  = attrs.get("extra_tags", [])
    is_cp       = "CP" in scene_type.upper()

    # ── Category: 8K, Hair, [Ethnicity…], [TitCats…], [Body…], Blowjob, [CumType] ──
    cat: list[str] = ["8K"]
    if hair == "Black Hair":
        cat.extend(["Asian", "Black Hair"])
    elif hair:
        cat.append(hair)
    cat.extend(ethnicity)
    cat.extend(tit_cats)
    for extra in ["Big Ass", "Milf", "Petite", "Curvy", "Hairy Pussy"]:
        if extra in body_extras:
            cat.append(extra)
    cat.append("Blowjob")
    if is_cp:
        cat.append("Creampie")

    # ── Tags: positions, Sexy Hair, [Sexy Eth…], POV, boobs, [Ass], [Hairy/Shaved], [Cum] ──
    tag: list[str] = [
        "POV BJ", "Dick Sucking", "POV BJ",
        "Reverse Cowgirl", "Cowgirl", "Missionary", "Doggy Style",
    ]
    if hair == "Black Hair":
        tag.append("Sexy Asian")
    elif hair:
        tag.append(f"Sexy {hair}")
    for eth in ethnicity:
        tag.append(f"Sexy {eth}")
    tag.append("POV")

    if fake_tits:
        tag.append("Big Boobs")
        tag.append("Fake Tits")
    else:
        for tit in tit_cats:
            tag.append({"Natural Tits": "Natural Boobs",
                        "Big Tits":     "Big Boobs",
                        "Small Tits":   "Small Boobs"}.get(tit, tit))

    if "Big Ass" in body_extras:
        tag.append("Ass")
    tag.append("Hairy Pussy" if "Hairy Pussy" in body_extras else "Shaved Pussy")
    if is_cp:
        tag.append("Cum in Pussy")
    if "Milf" in body_extras:
        tag.append("Milf Porn")
    tag.extend(extra_tags)

    return ", ".join(cat), ", ".join(tag)


def _build_vrh_cat_tags(attrs: dict, scene_type: str) -> tuple[str, str]:
    hair        = attrs.get("hair", "")
    ethnicity   = attrs.get("ethnicity", [])
    tit_cats    = attrs.get("tit_cats", [])
    body_extras = attrs.get("body_extras", [])
    fake_tits   = attrs.get("fake_tits", False)
    extra_tags  = attrs.get("extra_tags", [])
    is_cp       = "CP" in scene_type.upper()

    # ── Category ──
    cat: list[str] = ["8K"]
    if hair == "Black Hair":
        cat.extend(["Brunette", "Asian"])
    elif hair:
        cat.append(hair)
    cat.extend(ethnicity)
    cat.extend(tit_cats)
    for extra in ["Big Ass", "Milf", "Hairy Pussy"]:
        if extra in body_extras:
            cat.append(extra)
    cat.append("Blowjob")
    cat.append("Hardcore")
    cat.append("Creampie" if is_cp else "Cumshot")

    # ── Tags ──
    tag: list[str] = []
    if hair == "Black Hair":
        tag.extend(["Sexy Brunette", "Sexy Asian"])
    elif hair:
        tag.append(f"Sexy {hair}")
    for eth in ethnicity:
        tag.append(f"Sexy {eth}")
    tag.extend(["POV", "POV BJ", "Dick Sucking",
                "Cowgirl", "Reverse Cowgirl", "Standing Missionary", "Doggystyle"])

    if fake_tits:
        tag.append("Big Boobs")
        tag.append("Fake Tits")
    else:
        for tit in tit_cats:
            tag.append({"Natural Tits": "Natural Boobs",
                        "Big Tits":     "Big Boobs",
                        "Small Tits":   "Small Boobs"}.get(tit, tit))

    if "Big Ass" in body_extras:
        tag.append("Ass")
    tag.append("Hairy Pussy" if "Hairy Pussy" in body_extras else "Shaved Pussy")
    if "Milf" in body_extras:
        tag.append("Milf Porn")
    tag.extend(extra_tags)
    if is_cp:
        tag.append("Cum in Pussy")

    return ", ".join(cat), ", ".join(tag)


def _build_vra_cat_tags(attrs: dict) -> tuple[str, str]:
    """VRA is always a Solo/masturbation scene."""
    hair        = attrs.get("hair", "")
    ethnicity   = attrs.get("ethnicity", [])
    tit_cats    = attrs.get("tit_cats", [])
    body_extras = attrs.get("body_extras", [])
    fake_tits   = attrs.get("fake_tits", False)
    extra_tags  = attrs.get("extra_tags", [])
    asian_bh    = (hair == "Black Hair")

    # ── Category: NO "8K" prefix; Asian/Black Hair skip Blowjob ──
    cat: list[str] = []
    if asian_bh:
        cat.extend(["Asian", "Black Hair"])
    else:
        if hair:
            cat.append(hair)
        cat.extend(ethnicity)
    cat.extend(tit_cats)
    for extra in ["Big Ass", "Milf", "Petite", "Curvy", "Hairy Pussy"]:
        if extra in body_extras:
            cat.append(extra)
    if not asian_bh:
        cat.append("Blowjob")
    cat.extend(["Masturbation", "Sex Toys"])

    # ── Tags: 8K, Solo, core sequence, Sexy Hair, … ──
    tag: list[str] = ["8K", "Solo", "Pussy Worship", "Toys", "Ken Doll", "Vibrator"]
    if asian_bh:
        tag.append("Sexy Asian")
    else:
        if hair:
            tag.append(f"Sexy {hair}")
        for eth in ethnicity:
            tag.append(f"Sexy {eth}")
    tag.extend(["Close-up", "Intimate", "Kissing",
                "Pussy Fingering", "Pussy Play", "Lingerie"])

    if fake_tits:
        tag.append("Big Boobs")
        tag.append("Fake Tits")
    else:
        for tit in tit_cats:
            tag.append({"Natural Tits": "Natural Boobs",
                        "Big Tits":     "Big Boobs",
                        "Small Tits":   "Small Boobs"}.get(tit, tit))

    tag.append("Hairy Pussy" if "Hairy Pussy" in body_extras else "Shaved Pussy")
    tag.extend(extra_tags)

    return ", ".join(cat), ", ".join(tag)


def _build_nnjoi_cat_tags(attrs: dict, phase: str) -> tuple[str, str]:
    """
    NNJOI category/tags.
    phase = "nice"    → Masturbation only; Intimate, Kissing, Tease
    phase = "naughty" → Masturbation, Sex Toys; Wank Porn, Dominant
    """
    hair        = attrs.get("hair", "")
    ethnicity   = attrs.get("ethnicity", [])
    tit_cats    = attrs.get("tit_cats", [])
    body_extras = attrs.get("body_extras", [])
    fake_tits   = attrs.get("fake_tits", False)

    # ── Category ──
    cat: list[str] = ["8K", "JOI"]
    if hair and hair != "Black Hair":
        cat.append(hair)
    cat.extend(tit_cats)
    for extra in ["Big Ass", "Curvy", "Hairy Pussy"]:
        if extra in body_extras:
            cat.append(extra)
    cat.append("Masturbation")
    if phase == "naughty":
        cat.append("Sex Toys")

    # ── Tags ──
    tag: list[str] = []
    if hair and hair != "Black Hair":
        tag.append(f"Sexy {hair}")
    for eth in ethnicity:
        tag.append(f"Sexy {eth}")
    tag.append("POV")

    if fake_tits:
        tag.append("Big Boobs")
        tag.append("Fake Tits")
    else:
        for tit in tit_cats:
            tag.append({"Natural Tits": "Natural Boobs",
                        "Big Tits":     "Big Boobs",
                        "Small Tits":   "Small Boobs"}.get(tit, tit))

    tag.append("JOI instructions")
    if phase == "nice":
        tag.extend(["Intimate", "Kissing", "Tease"])
    else:
        tag.extend(["Wank Porn", "Dominant"])
    if "Hairy Pussy" in body_extras:
        tag.append("Hairy Pussy")

    return ", ".join(cat), ", ".join(tag)


def build_category_tags(
    tab_name: str,
    scene_type: str,
    female: str,
    performer_lookup: dict[str, dict],
    phase: str = "",
) -> tuple[str, str]:
    """Dispatch to the correct studio builder. Returns ("", "") if attrs unknown."""
    attrs = performer_lookup.get(female, {})
    if not attrs:
        log.warning(f"  No attrs for '{female}' — category/tags left blank")
        return "", ""

    if tab_name == "FPVR":
        return _build_fpvr_cat_tags(attrs, scene_type)
    if tab_name == "VRH":
        return _build_vrh_cat_tags(attrs, scene_type)
    if tab_name == "VRA":
        return _build_vra_cat_tags(attrs)
    if tab_name == "NNJOI":
        return _build_nnjoi_cat_tags(attrs, phase)

    return "", ""


# ── FPVR location parser ───────────────────────────────────────────────────────

def parse_fpvr_location(destination: str) -> tuple[str, str, str, str]:
    """
    Convert a Scripts-sheet Destination string (e.g. "Las Vegas, NV" or
    "Salvador, BR") into (continent, country, region, city).
    Returns four empty strings if the destination is blank or unrecognised.
    """
    dest = destination.strip()
    if not dest or dest.upper() in ("PSE", ""):
        return "", "", "", ""

    parts = [p.strip() for p in dest.split(",")]
    if len(parts) < 2:
        return "", "", "", ""

    city = parts[0]
    code = parts[1].upper()

    # US state?
    if code in US_STATES:
        return "North America", "United States", US_STATES[code], city

    # Known international location?
    key = f"{city}, {code}"
    if key in INTL_LOCATIONS:
        return INTL_LOCATIONS[key]

    log.warning(f"  Unknown FPVR destination '{dest}' — location columns will be blank")
    return "", "", "", ""


# ── Auto title generation ─────────────────────────────────────────────────────

_TITLE_SYSTEMS = {
    "VRHush": (
        "Generate exactly ONE scene title for VRHush (premium VR adult studio). "
        "Rules: 2-3 words ONLY, clever double-entendre/wordplay preferred, catchy and memorable. "
        "No performer names. Style reference: Heat By Design, Born To Breed, Under Her Spell, "
        "Intimate Renderings, Content Cutie, Nailing the Interview. "
        "Respond with ONLY the title."
    ),
    "FuckPassVR": (
        "Generate exactly ONE scene title for FuckPassVR (VR travel/adventure adult studio). "
        "Rules: 2-5 words, travel/destination vibes when applicable, clever wordplay. "
        "No performer names. Style reference: Eager Beaver, Deep Devotion, Behind the Curtain, "
        "The Bouncing Layover, Pressing Dripping Matters, The Night is Young. "
        "Respond with ONLY the title."
    ),
    "VRAllure": (
        "Generate exactly ONE scene title for VRAllure (intimate solo VR studio). "
        "Rules: 2-3 words ONLY, sensual/elegant, not crass. "
        "No performer names. Style reference: Sweet Surrender, Rise and Grind, Always on Top, "
        "Potent Curves, Hovering With Intent, A Swift Release. "
        "Respond with ONLY the title."
    ),
    "NaughtyJOI": None,  # NJOI titles have a different paired format, handled separately
}


def generate_title(studio: str, female: str, theme: str, plot: str) -> str:
    """Generate a scene title using Claude. Returns empty string on failure."""
    system = _TITLE_SYSTEMS.get(studio)
    if not system:
        return ""  # NJOI titles handled differently

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        log.warning("  ANTHROPIC_API_KEY not set — cannot generate title")
        return ""

    user_msg = f"Performer: {female}\nTheme: {theme}\nPlot: {plot[:400]}"

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=30,
            system=system,
            messages=[{"role": "user", "content": user_msg}]
        )
        title = resp.content[0].text.strip().strip('"').strip("'")
        # Reject responses that look like prices, numbers, or non-titles
        import re as _re
        if _re.search(r'^\$[\d,]+(\.\d+)?$', title) or _re.search(r'^\d', title):
            log.warning(f"  Title generation returned non-title value '{title}' — discarding")
            return ""
        log.info(f"  Generated title: '{title}' for {studio}/{female}")
        return title
    except Exception as e:
        log.warning(f"  Title generation failed: {e}")
        return ""


# ── Step 1 – Find today's shoots ──────────────────────────────────────────────

def get_todays_shoots(gc: gspread.Client) -> list[dict]:
    """Return a list of shoot dicts for rows whose date == today."""
    sh = gc.open_by_key(SCRIPTS_SHEET_ID)
    try:
        ws = sh.worksheet(MONTH_TAB_NAME)
    except gspread.exceptions.WorksheetNotFound:
        log.error(f"Tab '{MONTH_TAB_NAME}' not found in 2026 Scripts sheet.")
        return []

    all_rows = _retry(ws.get_all_values)
    shoots: list[dict] = []

    for i, row in enumerate(all_rows, start=1):
        date_cell = row[COL_DATE].strip() if len(row) > COL_DATE else ""
        if _parse_date_cell(date_cell) != TODAY:
            continue

        studio      = row[COL_STUDIO].strip()      if len(row) > COL_STUDIO      else ""
        female      = row[COL_FEMALE].strip()      if len(row) > COL_FEMALE      else ""
        male        = row[COL_MALE].strip()        if len(row) > COL_MALE        else ""
        destination = row[COL_DESTINATION].strip() if len(row) > COL_DESTINATION else ""
        scene_type  = row[COL_TYPE].strip()        if len(row) > COL_TYPE        else "BG"

        if studio not in STUDIO_MAP:
            if studio:
                log.warning(f"  Row {i}: unknown studio '{studio}' – skipping")
            continue

        theme       = row[COL_THEME].strip()       if len(row) > COL_THEME       else ""
        plot        = row[COL_PLOT].strip()        if len(row) > COL_PLOT        else ""
        title       = row[COL_TITLE].strip()       if len(row) > COL_TITLE       else ""

        shoots.append({
            "row": i, "studio": studio,
            "female": female, "male": male,
            "destination": destination,
            "type": scene_type,
            "theme": theme, "plot": plot, "title": title,
        })

    return shoots


# ── Step 2 – Pre-check ────────────────────────────────────────────────────────

def precheck(
    grail_sh: gspread.Spreadsheet,
    tabs_needed: set[str],
) -> tuple[dict, dict]:
    """Open each needed tab, compute stats, abort if duplicates exist."""
    stats:      dict[str, dict]               = {}
    worksheets: dict[str, gspread.Worksheet]  = {}

    for tab_name in tabs_needed:
        ws = grail_sh.worksheet(tab_name)
        worksheets[tab_name] = ws
        stats[tab_name] = _tab_stats(ws)
        time.sleep(0.5)

    log.info("── Pre-check ──")
    has_dupes = False
    for tab, st in stats.items():
        if st["dupes"]:
            log.error(f"  {tab}: maxId={st['maxId']} — DUPLICATES: {st['dupes']}")
            has_dupes = True
        else:
            log.info(f"  {tab}: maxId={st['maxId']} — no dupes ✓")

    if has_dupes:
        log.error("STOPPING — duplicates detected. Investigate before adding rows.")
        sys.exit(1)

    return stats, worksheets


# ── Step 3 – Build rows ───────────────────────────────────────────────────────

def build_rows(
    shoots: list[dict],
    pre_stats: dict,
    performer_lookup: dict[str, dict],
) -> tuple[dict, list]:
    """
    Compute rows to append, grouped by tab.
    Returns (rows_by_tab, added_report).
    """
    next_id:     dict[str, int]  = {tab: st["maxId"] + 1 for tab, st in pre_stats.items()}
    rows_by_tab: dict[str, list] = {tab: [] for tab in pre_stats}
    added_report: list[dict]     = []

    for shoot in shoots:
        tab_name, site_code, n_rows = STUDIO_MAP[shoot["studio"]]
        female      = shoot["female"]
        male        = shoot["male"]
        performers  = female
        scene_type  = shoot.get("type", "BG")
        destination = shoot.get("destination", "")

        if n_rows == 1:
            rid = next_id[tab_name]
            cat, tags = build_category_tags(tab_name, scene_type, female, performer_lookup)

            # Auto-generate title if script has theme/plot and no title yet
            title = shoot.get("title", "")
            if not title and (shoot.get("theme") or shoot.get("plot")):
                title = generate_title(shoot["studio"], female,
                                       shoot.get("theme", ""), shoot.get("plot", ""))
                time.sleep(0.5)  # rate limit

            if tab_name == "FPVR":
                continent, country, region, city = parse_fpvr_location(destination)
                row_data = [site_code, rid, "", title, performers,
                            cat, tags, continent, country, region, city]
            else:
                row_data = [site_code, rid, "", title, performers, cat, tags]

            rows_by_tab[tab_name].append(row_data)
            added_report.append({
                "tab": tab_name, "id": rid,
                "performers": performers, "label": "",
                "title": title,
                "cat": cat, "tags": tags,
            })
            next_id[tab_name] += 1

        else:  # NaughtyJOI – two consecutive rows
            nice_id    = next_id[tab_name]
            naughty_id = nice_id + 1

            nice_cat, nice_tags       = build_category_tags(tab_name, scene_type, female,
                                                             performer_lookup, "nice")
            naughty_cat, naughty_tags = build_category_tags(tab_name, scene_type, female,
                                                             performer_lookup, "naughty")

            rows_by_tab[tab_name].append(
                [site_code, nice_id,    "", "", performers, nice_cat,    nice_tags])
            rows_by_tab[tab_name].append(
                [site_code, naughty_id, "", "", performers, naughty_cat, naughty_tags])

            added_report.append({
                "tab": tab_name, "id": nice_id,
                "performers": performers, "label": "[Nice]",
                "cat": nice_cat, "tags": nice_tags,
            })
            added_report.append({
                "tab": tab_name, "id": naughty_id,
                "performers": performers, "label": "[Naughty]",
                "cat": naughty_cat, "tags": naughty_tags,
            })
            next_id[tab_name] += 2

    return rows_by_tab, added_report


# ── Formatting helper ─────────────────────────────────────────────────────────

def _apply_row_formatting(ws: gspread.Worksheet,
                           first_row: int, n_rows: int, tab_name: str):
    """Apply column alignment to the newly written rows."""
    last_row = first_row + n_rows - 1
    aligns   = TAB_COL_ALIGN.get(
        tab_name,
        ["CENTER", "CENTER", "CENTER", "LEFT", "LEFT", "LEFT", "LEFT"],
    )

    formats = []
    for col_idx, alignment in enumerate(aligns):
        col_letter = ALL_COL_LETTERS[col_idx]
        cell_range = f"{col_letter}{first_row}:{col_letter}{last_row}"
        formats.append({"range": cell_range, "format": {"horizontalAlignment": alignment}})

    _retry(lambda f=formats: ws.batch_format(f))
    end_col = ALL_COL_LETTERS[len(aligns) - 1]
    log.info(f"  Formatting applied to {tab_name}!A{first_row}:{end_col}{last_row}")


def write_rows(rows_by_tab: dict, worksheets: dict, dry_run: bool):
    for tab_name, rows in rows_by_tab.items():
        if not rows:
            continue
        if dry_run:
            for r in rows:
                log.info(f"  [DRY RUN] {tab_name} ← {r}")
        else:
            log.info(f"  Appending {len(rows)} row(s) to {tab_name} …")
            ws   = worksheets[tab_name]
            resp = _retry(lambda w=ws, r=rows: w.append_rows(
                r, value_input_option="RAW", table_range="A1",
            ))
            updated_range = resp.get("updates", {}).get("updatedRange", "")
            try:
                range_part = updated_range.split("!")[-1]
                first_row  = int("".join(filter(str.isdigit, range_part.split(":")[0])))
            except (IndexError, ValueError):
                log.warning(f"  Could not parse range '{updated_range}' — skipping format")
                first_row = None

            if first_row:
                time.sleep(0.5)
                _apply_row_formatting(ws, first_row, len(rows), tab_name)
            time.sleep(1)


# ── Step 4 – Post-check ───────────────────────────────────────────────────────

def postcheck(worksheets: dict) -> dict:
    time.sleep(2)
    post_stats: dict[str, dict] = {}
    log.info("── Post-check ──")
    any_dupes = False
    for tab_name, ws in worksheets.items():
        st = _tab_stats(ws)
        post_stats[tab_name] = st
        if st["dupes"]:
            log.error(f"  {tab_name}: maxId={st['maxId']} — DUPLICATES: {st['dupes']}")
            any_dupes = True
        else:
            log.info(f"  {tab_name}: maxId={st['maxId']} — no dupes ✓")
        time.sleep(0.5)
    if any_dupes:
        log.error("WARNING — duplicates found after write. Manual review required.")
    return post_stats


# ── Report ─────────────────────────────────────────────────────────────────────

def print_report(
    added_report: list[dict],
    pre_stats: dict,
    post_stats: dict | None,
    dry_run: bool,
):
    tabs_touched = sorted(pre_stats.keys())
    all_tabs     = sorted({v[0] for v in STUDIO_MAP.values()})
    untouched    = sorted(set(all_tabs) - set(tabs_touched))

    pre_line = ", ".join(
        f"{t} maxId={pre_stats[t]['maxId']}" for t in tabs_touched
    ) + " — no dupes ✓"

    if post_stats and not dry_run:
        post_line = ", ".join(
            f"{t} maxId={post_stats[t]['maxId']}" for t in tabs_touched
        )
        any_post_dupes = any(post_stats[t]["dupes"] for t in tabs_touched)
        post_line += " — no dupes ✓" if not any_post_dupes else " — DUPES FOUND ⚠️"
    else:
        post_line = "(dry run – no writes)"

    lines = [
        "=" * 55,
        f"{'[DRY RUN] ' if dry_run else ''}✅ Daily Grail Update – {TODAY_DISPLAY}",
        "",
        f"Pre-check:  {pre_line}",
        f"Post-check: {post_line}",
        "",
        "Added:",
    ]

    for r in added_report:
        prefix = r["tab"].replace("NNJOI", "NJOI")
        id_str = f"{prefix}{r['id']:04d}"
        label  = f"  {r['label']}" if r["label"] else ""
        lines.append(f"  {id_str}{label} — {r['performers']}")
        if r.get("cat"):
            lines.append(f"    Cat:  {r['cat']}")
        if r.get("tags"):
            lines.append(f"    Tags: {r['tags']}")

    if untouched:
        lines.append(f"\nNo new scenes for: {', '.join(untouched)}")

    report = "\n".join(lines)
    print("\n" + report + "\n")
    log.info(report)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Daily Grail ID updater")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without touching the sheet")
    args = parser.parse_args()

    mode = "DRY RUN" if args.dry_run else "LIVE"
    log.info(f"=== Daily Grail Update – {TODAY_DISPLAY} ({mode}) ===")

    gc = get_client()

    # 1 – Find today's shoots
    shoots = get_todays_shoots(gc)
    if not shoots:
        msg = "No scenes scheduled for today — no Grail entries added."
        log.info(msg)
        print(msg)
        return

    log.info(f"Found {len(shoots)} shoot(s): {[s['studio'] for s in shoots]}")

    # 2 – Open both master sheets and build performer attribute lookup
    log.info("Building performer attribute lookup …")
    grail_sh   = gc.open_by_key(GRAIL_SHEET_ID)
    booking_sh = gc.open_by_key(BOOKING_SHEET_ID)
    performer_lookup = build_performer_lookup(grail_sh, booking_sh)
    log.info(f"  Total performers in lookup: {len(performer_lookup)}")

    # 3 – Pre-check for the tabs we need today
    tabs_needed = {STUDIO_MAP[s["studio"]][0] for s in shoots}
    pre_stats, worksheets = precheck(grail_sh, tabs_needed)

    # 4 – Build rows
    rows_by_tab, added_report = build_rows(shoots, pre_stats, performer_lookup)

    # 5 – Write
    write_rows(rows_by_tab, worksheets, args.dry_run)

    # 6 – Post-check
    post_stats = postcheck(worksheets) if not args.dry_run else None

    # 7 – Final report
    print_report(added_report, pre_stats, post_stats, args.dry_run)


if __name__ == "__main__":
    main()
