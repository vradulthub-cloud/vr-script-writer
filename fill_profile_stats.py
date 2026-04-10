#!/usr/bin/env python3
"""
fill_profile_stats.py
=====================
Scrapes every model's profile page across all 13 agency tabs and fills in:
  Height | Weight | Measurements | Hair | Eyes | Natural Breasts | Tattoos | Shoe Size | Available For

Also removes any model whose row has a "remove" flag or who is no longer
on the agency site (handled separately by update_roster.py).

Run AFTER add_profile_columns.py has added the new columns.

Usage:
    python3 /Users/andrewninn/Scripts/fill_profile_stats.py
    python3 /Users/andrewninn/Scripts/fill_profile_stats.py --tab "OC Models"
    python3 /Users/andrewninn/Scripts/fill_profile_stats.py --dry-run

Requirements (already installed for update_roster.py):
    pip3 install gspread google-auth playwright beautifulsoup4 --break-system-packages
    python3 -m playwright install chromium
"""

import argparse
import logging
import os
import re
import time
from pathlib import Path

import gspread
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

# ── Config ─────────────────────────────────────────────────────────────────────
SPREADSHEET_ID       = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
SERVICE_ACCOUNT_FILE = Path(__file__).parent / "service_account.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
HEADER_ROW     = 3
DATA_START_ROW = 4
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# These are the new profile columns we care about (must already exist in sheet)
PROFILE_FIELDS = [
    "Age", "Location",
    "Height", "Weight", "Measurements", "Hair", "Eyes",
    "Natural Breasts", "Tattoos", "Shoe Size", "Available For",
]

# Fields that Babepedia can reliably provide (used for gap-filling after agency scraping)
BABEPEDIA_FIELDS = {"Age", "Height", "Weight", "Measurements", "Hair", "Eyes", "Natural Breasts", "Tattoos"}

# 101 Models: profile URLs use numeric t_id, not a name slug.
# This cache is populated once per run by load_101_models_id_map().
_101_id_map: dict = {}   # model_name.lower() → t_id string

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def name_to_slug(name: str) -> str:
    """'Adriana Maya' → 'adriana-maya'"""
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def first_text(soup, *selectors):
    """Try each CSS selector, return cleaned text of first match."""
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            return clean(el.get_text(separator=" "))
    return ""


def label_value(soup, label: str) -> str:
    """Find a <th> or <dt> or label whose text contains `label`, return sibling value."""
    label_l = label.lower()
    for tag in soup.find_all(["th", "dt", "td", "li", "div", "span", "p"]):
        text = clean(tag.get_text())
        if text.lower().startswith(label_l) and len(text) < len(label) + 60:
            # Try next sibling
            sib = tag.find_next_sibling()
            if sib:
                val = clean(sib.get_text())
                if val:
                    return val
            # Or colon-split in same element
            if ":" in text:
                return clean(text.split(":", 1)[1])
    return ""


# ── Site-specific profile scrapers ────────────────────────────────────────────

def _scrape_oc_models(soup: BeautifulSoup) -> dict:
    """ocmodeling.com/model/[slug]/
    Structure: <ul> with <li> items each containing a <label> + sibling text node or span.
    Available For is a second <ul> whose first <li> has label 'Available For:',
    followed by individual <li> items for each scene type.
    """
    data = {}
    FIELD_MAP = {
        "age":        "Age",
        "hair color": "Hair",
        "eye color":  "Eyes",
        "weight":     "Weight",
        "natural breasts": "Natural Breasts",
        "breast size": "Measurements",
        "measurements": "Measurements",
        "height":     "Height",
        "tattoos":    "Tattoos",
        "shoe size":  "Shoe Size",
        "location":   "Location",
    }
    for li in soup.select("li"):
        label_el = li.find("label")
        if not label_el:
            continue
        field_raw = clean(label_el.get_text()).rstrip(":").lower()
        col = FIELD_MAP.get(field_raw)
        if not col:
            continue
        # Value = everything in the <li> minus the label text
        full = clean(li.get_text())
        label_text = clean(label_el.get_text())
        val = clean(full[len(label_text):].lstrip(":").strip())
        if val:
            data[col] = val

    # Available For: find the <ul> that starts with label "Available For:"
    avail_label = soup.find("label", string=re.compile(r"available for", re.I))
    if avail_label:
        ul = avail_label.find_parent("ul")
        if ul:
            items = [
                clean(li.get_text())
                for li in ul.find_all("li")
                if not li.find("label") and clean(li.get_text())
            ]
            if items:
                data["Available For"] = ", ".join(items)
    return data


def _scrape_hussie_models(soup: BeautifulSoup) -> dict:
    """hussiemodels.com/model/[slug]
    Table with th=field, td=value. Available For is a single td with comma-separated text.
    Weight often has "lbs" appended (e.g. "130lbs") — strip it to just the number.
    Age does not appear on model pages; skip it.
    Location appears as a "LOCATIONS" section heading followed by one city per line.
    """
    data = {}
    lines = [clean(l) for l in soup.get_text(separator="\n").splitlines() if clean(l)]

    for i, line in enumerate(lines):
        ll = line.lower()
        nxt = lines[i+1] if i + 1 < len(lines) else ""

        if ll == "height" and nxt:
            data["Height"] = nxt
        elif ll == "weight" and nxt:
            # Strip trailing "lbs" (e.g. "130lbs" → "130")
            data["Weight"] = re.sub(r"\s*lbs?\s*$", "", nxt, flags=re.I).strip()
        elif ll in ("chest", "bust") and nxt:
            data["Measurements"] = nxt
        elif ll == "shoes" and nxt:
            data["Shoe Size"] = nxt
        elif ll == "tattoos" and nxt:
            data["Tattoos"] = nxt
        elif ll == "available for" and nxt:
            data["Available For"] = nxt

    return data


def _scrape_nexxxt_level(soup: BeautifulSoup) -> dict:
    """nexxxtleveltalentagency.com/models/[slug]/
    Structure: <ul class="model-single__stats-item-wrapper"> with <li> children where each
    <li> has two child elements: [label_span, value_span].
    Available For: <div class="model-single__casting-list"> with <br>-separated items.
    Location: appears in a Socials block as 'Location' heading then city on next line.
    """
    data = {}

    # Stats: each <li class="brxe-div model-single__stats-item"> has label + value children
    for li in soup.select("li.model-single__stats-item, li.brxe-div"):
        children = [clean(el.get_text()) for el in li.find_all(True, recursive=False)]
        children = [c for c in children if c]
        if len(children) >= 2:
            label = children[0].rstrip(":").strip().lower()
            value = children[1].strip()
        elif len(children) == 1 and ":" in children[0]:
            label, _, value = children[0].partition(":")
            label = label.strip().lower()
            value = value.strip()
        else:
            continue
        if not value:
            continue
        if label == "age":           data["Age"] = value
        elif label == "height":      data["Height"] = value
        elif label == "weight":      data["Weight"] = value
        elif label == "measurements":data["Measurements"] = value
        elif label == "shoe size":   data["Shoe Size"] = value
        elif label in ("hair", "hair color"): data["Hair"] = value
        elif label in ("eyes", "eye color"):  data["Eyes"] = value

    # Location: in the Socials block — "Location" heading, city on next non-empty line
    lines = [clean(l) for l in soup.get_text(separator="\n").splitlines() if clean(l)]
    for i, line in enumerate(lines):
        if line.lower() == "location" and i + 1 < len(lines):
            loc = lines[i + 1]
            if loc.lower() not in ("yes", "no", "incorporated", "twitter", "instagram"):
                data["Location"] = loc
            break

    # Normalize height spacing: "5' 4\"" → "5'4\""
    if "Height" in data:
        data["Height"] = re.sub(r"(\d+)'\s+(\d+)", r"\1'\2", data["Height"])

    # Available For: <div class="*casting*"> with <br>-separated items.
    # The parent container may include an "Available For:" heading — strip it.
    casting_div = soup.find("div", class_=re.compile(r"casting"))
    if casting_div:
        items = [clean(t) for t in casting_div.get_text(separator="\n").splitlines()
                 if clean(t) and not re.match(r"available for\s*:?\s*$", clean(t), re.I)]
        if items:
            data["Available For"] = ", ".join(items)
    else:
        # Fallback: h3/heading "Available For:" then sibling content
        avail_h = soup.find(["h3", "h4"], string=re.compile(r"available for", re.I))
        if avail_h:
            parent = avail_h.find_parent()
            if parent:
                items = [clean(t) for t in parent.get_text(separator="\n").splitlines()
                         if clean(t) and not re.match(r"available for", clean(t), re.I)]
                if items:
                    data["Available For"] = ", ".join(items)
    return data


def _scrape_foxxx_modeling(soup: BeautifulSoup) -> dict:
    """foxxxmodeling.com/model-stats-profile-page/[slug]
    Wix site: all stats are in a SINGLE concatenated rich-text span with no separators:
      'Age- 20Weight- 100 (lbs)Height- 5\'5"(Feet/Inches)Dress Size- 1 (US)...'
    Available For: separate Wix element with 'AVAILABLE FOR:' then comma-separated list.
    Many slugs return 404 when a model has left the agency — detect and skip cleanly.
    """
    page_text = clean(soup.get_text(separator=" "))
    if re.search(r"can't find this page|page not found|404", page_text, re.I) or len(page_text) < 150:
        log.warning("      [Foxxx] 404 — model no longer on Foxxx roster. Skipping.")
        return {}

    data = {}
    FOXXX_FIELDS = ["Age", "Weight", "Height", "Dress Size", "Shoe Size", "Cup Size", "All Natural"]
    field_pat = "(" + "|".join(re.escape(f) for f in FOXXX_FIELDS) + r")\s*-\s*"

    # Stats live in a single concatenated Wix text element.
    # IMPORTANT: split on \u200b BEFORE calling clean(), because clean() converts
    # zero-width spaces to regular spaces which breaks the boundary detection.
    stats_text = ""
    for el in soup.find_all(["span", "p", "div"]):
        raw = el.get_text()
        t = clean(raw)
        if re.search(r"(?:Age|Weight|Height)\s*-\s*\d", t) and len(t) < 600:
            # Split on \u200b in raw text to cut off booking/nav section, then clean
            stats_text = clean(raw.split("\u200b")[0])
            break

    if not stats_text:
        # Fallback: join all text, split on \u200b before cleaning
        raw_all = soup.get_text(separator=" ")
        stats_text = clean(raw_all.split("\u200b")[0])

    if stats_text:
        # Strip "STATS:" prefix if present
        stats_text = re.sub(r"^.*?STATS:\s*", "", stats_text, flags=re.I).strip()
        parts = re.split(field_pat, stats_text)
        # parts = ['prefix', 'FieldName', 'value', 'FieldName', 'value', ...]
        for i in range(1, len(parts) - 1, 2):
            field = parts[i].strip()
            value = clean(parts[i + 1]) if i + 1 < len(parts) else ""
            # Strip trailing unit markers like "(lbs)", "(US)", "(Feet/Inches)"
            value = re.sub(r"\s*\([^)]+\)\s*$", "", value).strip()
            if not value:
                continue
            if field == "Age":          data["Age"] = value
            elif field == "Height":     data["Height"] = value
            elif field == "Weight":     data["Weight"] = value
            elif field == "Cup Size":   data["Measurements"] = value
            elif field == "All Natural":data["Natural Breasts"] = value
            elif field == "Shoe Size":  data["Shoe Size"] = value

    # Available For: "AVAILABLE FOR:" followed by comma-separated list (same or next line)
    capture = False
    for line in soup.get_text(separator="\n").splitlines():
        line = clean(line)
        if not line:
            continue
        m = re.match(r"available for\s*:?\s*(.*)", line, re.I)
        if m:
            rest = m.group(1).strip()
            if rest:
                data["Available For"] = rest
                break
            capture = True
            continue
        if capture and not re.search(r"^(international|date available|book model|not an escort)", line, re.I):
            data["Available For"] = line
            break
    return data


def _scrape_zen_models(soup: BeautifulSoup) -> dict:
    """zenmodels.org/our-models/[slug]/
    Most pages use inline 'Label: Value'. Some pages split the field across lines:
      - 'Age:' on one line, '22' on the next
      - 'Height' on one line, ': 5\'4"' (colon-prefix) on the next
      - 'Weight' on one line, ':100lbs' on the next
    Handle all three patterns with index-based lookahead.
    """
    data = {}
    bust, cup = "", ""
    lines = [clean(l) for l in soup.get_text(separator="\n").splitlines() if clean(l)]
    i = 0
    while i < len(lines):
        line = lines[i]
        nxt  = lines[i + 1] if i + 1 < len(lines) else ""

        k, v = "", ""

        if ":" in line:
            k, _, v = line.partition(":")
            k, v = k.strip().lower(), v.strip()
            if not v:
                # Value on the next line (unless next line itself starts with ":")
                if nxt and not nxt.startswith(":"):
                    v = nxt
        elif nxt.startswith(":"):
            # Label on this line, ': Value' on the next line
            k = line.strip().lower()
            v = nxt.lstrip(":").strip()
            i += 1  # consume the lookahead line

        if k and v:
            if k == "age":             data["Age"] = v
            elif k == "height":        data["Height"] = v
            elif k == "weight":
                # Some pages append 'lbs' (e.g. ':100lbs') — strip it
                data["Weight"] = re.sub(r"\s*lbs?\s*$", "", v, flags=re.I).strip()
            elif k == "bust":          bust = v.rstrip('"″')
            elif k == "cup size":      cup = v
            elif k in ("hair color", "hair"): data["Hair"] = v
            elif k in ("eye color", "eyes"):  data["Eyes"] = v
            elif k == "shoe size":     data["Shoe Size"] = v
            elif k in ("city", "location"):   data["Location"] = v
            elif k == "available for":
                # Values separated by ' / ' or '/ '
                data["Available For"] = re.sub(r"\s*/\s*", ", ", v).strip(", ")
        i += 1

    # Build measurements from bust + cup
    if bust or cup:
        data["Measurements"] = f"{bust}{cup}".strip()
    return data


def _scrape_101_models(soup: BeautifulSoup) -> dict:
    """101modeling.com/site/talent/view.php?t_id=...&pageType=profile
    Stats section has plain 'Label: Value' text lines.
    Height is displayed as '5 5' (feet space inches) — convert to 5'5".
    Measurements assembled from Bust + Waist + Hips fields.
    Available For: <li> items below the 'Available for' heading.
    """
    data = {}
    bust, waist, hips = "", "", ""

    for line in [clean(l) for l in soup.get_text(separator="\n").splitlines() if clean(l)]:
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip().lower(), v.strip()
        if not v:
            continue
        if k == "height":
            # Site renders 5'5" as "5 5" (feet, space, inches)
            hm = re.match(r"(\d)\s+(\d{1,2})$", v)
            data["Height"] = f"{hm.group(1)}'{hm.group(2)}\"" if hm else v
        elif k == "bust":
            bust = v                         # e.g. "30B"
        elif k == "waist":
            waist = v
        elif k == "hips":
            hips = v
        elif k == "weight":
            data["Weight"] = re.sub(r"\s*lbs?\s*$", "", v, flags=re.I).strip()
        elif k == "age":
            data["Age"] = v
        # Dress Size intentionally skipped

    # Build measurements from bust/waist/hips
    parts = [x for x in [bust, waist, hips] if x]
    if parts:
        data["Measurements"] = "-".join(parts)

    # Available For: <h3>Available for</h3> followed by a <p> with <br>-separated items
    avail_h = soup.find(["h3", "h4", "h2", "strong", "b"],
                        string=re.compile(r"available for", re.I))
    if avail_h:
        # The <p> sibling immediately after the heading contains br-separated items
        p = avail_h.find_next_sibling("p")
        if not p:
            # Fallback: first <p> inside the parent container
            container = avail_h.find_parent()
            if container:
                p = container.find("p")
        if p:
            items = [clean(t) for t in p.get_text(separator="\n").splitlines() if clean(t)]
            if items:
                data["Available For"] = ", ".join(items)
    return data


def _scrape_coxxx_models(soup: BeautifulSoup) -> dict:
    """coxxxmodels.com/portfolio/[slug]  (note: THREE x's)
    Stats rendered as <div class="jet-listing-dynamic-field__content"> elements,
    each containing 'Label : Value' text (with spaces around the colon).
    Available For: a single div containing bullet-separated (•) scene types.
    """
    data = {}

    divs = soup.select("div.jet-listing-dynamic-field__content")
    if not divs:
        return {}

    for div in divs:
        txt = clean(div.get_text())
        if not txt or ":" not in txt:
            # Could be the "Available For" bullet-list div
            if "•" in txt:
                items = [clean(p) for p in txt.split("•") if clean(p)]
                # Filter generic header words
                items = [it for it in items if it.lower() not in ("appearances",)]
                if items:
                    data["Available For"] = ", ".join(items)
            continue

        k, _, v = txt.partition(":")
        k, v = k.strip().lower(), v.strip()
        if not v:
            continue

        if k == "age":
            # "34 yrs." → "34"
            m = re.match(r"(\d+)", v)
            if m:
                data["Age"] = m.group(1)
        elif k == "height":
            # "5′ 7″" → normalize to 5'7"
            v = v.replace("′", "'").replace("″", '"').replace("\u2032", "'").replace("\u2033", '"')
            data["Height"] = v
        elif k == "weight":
            # "135 lbs." → "135"
            m = re.match(r"(\d+)", v)
            if m:
                data["Weight"] = m.group(1)
        elif k == "bra":
            # "36 B • Cup" → "36B"
            bra = re.sub(r"\s*•.*$", "", v).strip()
            bra = re.sub(r"\s+", "", bra)
            data["Measurements"] = bra
        elif k == "location":
            data["Location"] = v
    return data


def _scrape_atmla(soup: BeautifulSoup) -> dict:
    """atmla.com/performers/female-models/[slug]/
    Stats table below photo: field names in one column, values in adjacent column.
    Natural Breasts / No Tattoos shown as badge buttons.
    Available For: list of items with circle bullets.
    """
    data = {}
    # Stats table: 3-col layout (label, value, label, value)
    lines = [clean(l) for l in soup.get_text(separator="\n").splitlines() if clean(l)]
    for i, line in enumerate(lines):
        ll = line.lower()
        nxt = lines[i+1] if i + 1 < len(lines) else ""
        if ll == "age":           data["Age"] = nxt
        elif ll == "height":      data["Height"] = nxt
        elif ll == "weight":      data["Weight"] = nxt
        elif ll == "measurements":data["Measurements"] = nxt
        elif ll == "hair":        data["Hair"] = nxt
        elif ll == "eyes":        data["Eyes"] = nxt
        elif ll == "shoe size":   data["Shoe Size"] = nxt
        elif ll == "location":    data["Location"] = nxt
        # Badges appear as standalone lines
        elif ll == "natural breasts": data["Natural Breasts"] = "Yes"
        elif ll == "no tattoos":      data["Tattoos"] = "No"

    # Available For: heading then circle-bullet items
    avail_heading = soup.find(string=re.compile(r"available for", re.I))
    if avail_heading:
        parent = avail_heading.find_parent()
        items = [clean(li.get_text()) for li in parent.find_all_next("li", limit=30)
                 if clean(li.get_text()) and len(clean(li.get_text())) < 60]
        if items:
            data["Available For"] = ", ".join(items)
    return data


def _scrape_model_service(soup: BeautifulSoup) -> dict:
    """themodelservice.com/model/[slug].html
    Grid with UPPERCASE labels (HEIGHT, WEIGHT, LOCATION, AGE, SCENE TYPE).
    Labels and values appear on consecutive lines in text.
    """
    data = {}
    lines = [clean(l) for l in soup.get_text(separator="\n").splitlines() if clean(l)]
    for i, line in enumerate(lines):
        ll = line.lower()
        nxt = lines[i+1] if i + 1 < len(lines) else ""
        if ll == "age":         data["Age"] = nxt
        elif ll == "height":
            # Strip trailing junk after a valid height (e.g. "5'925''" → "5'9").
            # The site sometimes appends extra text/footnotes to the same value node.
            hm = re.match(r"(\d+'\s*(?:10|11|[0-9])['\"]{0,2})", nxt)
            data["Height"] = hm.group(1).strip() if hm else nxt
        elif ll == "weight":    data["Weight"] = nxt
        elif ll == "location":  data["Location"] = nxt
        elif ll == "scene type":data["Available For"] = nxt
    return data


def _scrape_east_coast_talent(soup: BeautifulSoup) -> dict:
    """eastcoasttalents.com/talent/[slug]/
    Stats live in <div class="brxe-text talent-single__stats-info"><p><strong>Label</strong>: Value</p></div>.
    Available For lives in <ul class="talent-single__availability-display"> with
    <li class="talent-single__availability-item-wrapper"><span>Item</span></li>.
    """
    data = {}
    FIELD_MAP = {
        "age": "Age", "height": "Height", "weight": "Weight",
        "measurements": "Measurements", "hair": "Hair", "eyes": "Eyes",
        "shoe size": "Shoe Size", "tattoos": "Tattoos",
        "natural breasts": "Natural Breasts", "location": "Location",
    }

    # Each stat div: <p><strong>Label</strong>: Value</p>
    for stat_div in soup.select("div.talent-single__stats-info, div[class*='stats-info']"):
        p = stat_div.find("p")
        if not p:
            continue
        strong = p.find("strong")
        if not strong:
            continue
        label = clean(strong.get_text()).rstrip(":").lower()
        col = FIELD_MAP.get(label)
        if not col:
            continue
        # Value = everything in <p> after the <strong> tag
        full = clean(p.get_text())
        label_text = clean(strong.get_text())
        val = clean(full[len(label_text):].lstrip(":").strip())
        if val:
            data[col] = val

    # Available For: <ul class="talent-single__availability-display"> with <li><span>Item</span></li>
    avail_ul = soup.select_one("ul[class*='availability-display'], ul[class*='availability']")
    if avail_ul:
        items = [clean(li.get_text()) for li in avail_ul.find_all("li") if clean(li.get_text())]
        if items:
            data["Available For"] = ", ".join(items)

    return data


def _scrape_bakery_talent(soup: BeautifulSoup) -> dict:
    """thebakerytalent.com/[slug]
    Plain 'Label: Value' lines. Measurements built from Bust+Waist+Hips.
    'Available for BG, GG, ...' at bottom (no colon after 'for').
    """
    data = {}
    bust, waist, hips = "", "", ""
    for line in soup.get_text(separator="\n").splitlines():
        line = clean(line)
        if not line:
            continue
        # Handle 'Available for ...' (no colon)
        m = re.match(r"available for\s+(.*)", line, re.I)
        if m:
            data["Available For"] = m.group(1).strip()
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip().lower(), v.strip()
        if not v:
            continue
        if k == "age":      data["Age"] = v
        elif k == "height":
            # Clip at end of valid height pattern (e.g. "5'9" not "5'927")
            # Inches are 0-11 so at most two digits; stop before any trailing bleed-in.
            hm = re.match(r"(\d+'\s*(?:10|11|[0-9])['\"]{0,2})", v)
            data["Height"] = hm.group(1).strip() if hm else v
        elif k in ("weight", "lbs"):
            data["Weight"] = v
        elif k == "bust":   bust = v
        elif k == "waist":  waist = v
        elif k == "hips":   hips = v
        elif k == "hair":   data["Hair"] = v
        elif k == "eyes":   data["Eyes"] = v
        elif k == "location":data["Location"] = v
        elif k in ("shoes", "shoe size"): data["Shoe Size"] = v

    parts = [x for x in [bust, waist, hips] if x]
    if parts:
        data["Measurements"] = "-".join(parts)
    return data


def _scrape_invision_models(soup: BeautifulSoup) -> dict:
    """invisionmodels.com/[slug]
    Plain 'Label: Value' or 'Label:Value' lines (no space around colon sometimes).
    Available For: list of uppercase items following 'Available For:' heading.
    """
    data = {}
    avail_lines = []
    capture_avail = False

    for line in soup.get_text(separator="\n").splitlines():
        line = clean(line)
        if not line:
            continue

        # Available For capture mode
        if re.match(r"available for", line, re.I):
            capture_avail = True
            rest = re.split(r"available for\s*:?\s*", line, flags=re.I, maxsplit=1)
            if len(rest) > 1 and rest[1].strip():
                avail_lines.append(rest[1].strip())
                capture_avail = False
            continue
        if capture_avail:
            if line and len(line) < 60 and not re.search(r"skills|age|hair|eye|height|bust|shoe|pant|dress|top\b|based", line, re.I):
                avail_lines.append(line)
            else:
                capture_avail = False

        # Stats lines
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip().lower(), v.strip()
        if not v:
            continue
        if k == "age":             data["Age"] = v
        elif k == "height":        data["Height"] = v
        elif k == "bust":          data["Measurements"] = v
        elif k == "hair":          data["Hair"] = v
        elif k == "eyes":          data["Eyes"] = v
        elif k == "location":      data["Location"] = v
        elif k in ("shoes", "shoe size"): data["Shoe Size"] = v

    if avail_lines:
        data["Available For"] = ", ".join(avail_lines)
    return data


def _scrape_spiegler_models(soup: BeautifulSoup) -> dict:
    """spieglergirls.com/html/[firstname].html
    Very minimal pages — only has 'Available for:' followed by items like '– Solo –'
    on separate lines. No physical stats.
    """
    data = {}
    lines = [clean(l) for l in soup.get_text(separator="\n").splitlines() if clean(l)]
    capture = False
    avail_items = []
    for line in lines:
        m = re.match(r"available for\s*:?\s*(.*)", line, re.I)
        if m:
            rest = m.group(1).strip()
            if rest:
                # Value on same line (comma-separated)
                avail_items.append(rest)
                break
            capture = True
            continue
        if capture:
            # Stop at non-item lines (contact/booking info).
            # "NOT AN ESCORT AGENCY" can appear as two separate lines: "NOT AN" and
            # "ESCORT AGENCY" (split at an internal newline in the <B> tag), so catch both.
            if re.search(r"NOT AN|ESCORT AGENCY|Producers|click|call Mark|spiegler|©", line, re.I):
                break
            # Strip "– … –" dash wrappers
            item = re.sub(r"^[–\-\s]+|[–\-\s]+$", "", line).strip()
            if item:
                avail_items.append(item)
    if avail_items:
        data["Available For"] = ", ".join(avail_items)
    return data


def _scrape_babepedia(soup: BeautifulSoup) -> dict:
    """babepedia.com/babe/[First_Last]
    Clean info-grid structure:
      <div class="info-item">
        <span class="label">Age:</span>
        <span class="value">28 years old</span>
      </div>
    Returns only the BABEPEDIA_FIELDS subset; Location/Available For/Shoe Size excluded.
    Returns {} when the page redirected to search results (model not in database).
    """
    # A valid profile page always has #personal-info-block
    if not soup.find(id="personal-info-block"):
        return {}

    data = {}
    for item in soup.select("div.info-item"):
        label_el = item.select_one("span.label")
        value_el = item.select_one("span.value")
        if not label_el or not value_el:
            continue
        label = clean(label_el.get_text()).rstrip(":").lower()
        value = clean(value_el.get_text())
        if not value:
            continue

        if label == "age":
            # "28 years old" → "28"
            m = re.match(r"(\d+)", value)
            if m:
                data["Age"] = m.group(1)

        elif label == "height":
            # "5'8\" (or 172 cm)" → "5'8\""  — strip parenthetical
            data["Height"] = value.split("(")[0].strip()

        elif label == "weight":
            # "125 lbs (or 57 kg)" → "125"
            m = re.match(r"(\d+)\s*lbs", value, re.I)
            if m:
                data["Weight"] = m.group(1)

        elif label == "measurements":
            data["Measurements"] = value

        elif label == "bra/cup size" and "Measurements" not in data:
            # Fallback if the measurements field wasn't listed separately
            data["Measurements"] = value

        elif label == "hair color":
            data["Hair"] = value

        elif label == "eye color":
            data["Eyes"] = value

        elif label == "boobs":
            # "Real/Natural" → Yes, "Fake/Augmented/Enhanced" → No
            if re.search(r"real|natural", value, re.I):
                data["Natural Breasts"] = "Yes"
            elif re.search(r"fake|augmented|enhanced|implant", value, re.I):
                data["Natural Breasts"] = "No"

        elif label == "tattoos":
            data["Tattoos"] = value

    return data


def load_101_models_id_map(page) -> None:
    """Scrape the 101 Modeling female-talent listing to build name → t_id cache.
    Handles simple pagination (next-page link).  Results stored in _101_id_map.
    """
    global _101_id_map
    if _101_id_map:
        return   # already loaded this run

    base = "https://101modeling.com"
    listing_url = f"{base}/site/female.php"
    page_num = 0

    while listing_url:
        try:
            try:
                page.wait_for_load_state("domcontentloaded", timeout=3_000)
            except Exception:
                pass
            page.goto(listing_url, wait_until="domcontentloaded", timeout=20_000)
            time.sleep(1.5)
            soup = BeautifulSoup(page.content(), "html.parser")
        except Exception as e:
            log.warning(f"[101 Models] Failed to load listing {listing_url}: {e}")
            break

        page_found = 0
        for a in soup.find_all("a", href=re.compile(r"t_id=\d+")):
            href = a.get("href", "")
            m = re.search(r"t_id=(\d+)", href)
            if not m:
                continue
            t_id = m.group(1)
            # Name from link text; fall back to img alt
            name = clean(a.get_text())
            if not name:
                img = a.find("img")
                if img:
                    name = clean(img.get("alt", ""))
            if not name or len(name) < 2:
                continue
            _101_id_map[name.lower().strip()] = t_id
            page_found += 1

        log.debug(f"[101 Models] Listing page {page_num}: {page_found} models found")

        # Follow "Next" pagination link if present
        next_a = soup.find("a", string=re.compile(r"next|»|›", re.I),
                            href=re.compile(r"pageType=female"))
        if next_a and page_found > 0:
            href = next_a.get("href", "")
            listing_url = href if href.startswith("http") else f"{base}/{href.lstrip('/')}"
            page_num += 1
        else:
            break

    log.info(f"[101 Models] ID map loaded: {len(_101_id_map)} models")


def scrape_babepedia_page(page, model_name: str) -> dict:
    """Navigate to Babepedia and extract supplemental stats for *model_name*.
    Returns {} when the model is not in the Babepedia database.

    Note: After an SSL/connection error on the previous page load, Playwright
    asynchronously navigates to chrome-error://chromewebdata/, which can interrupt
    the next page.goto() call.  We wait for the browser to reach a stable state
    first (page.wait_for_load_state) before loading Babepedia.
    """
    slug = "_".join(model_name.strip().split())
    url = f"https://www.babepedia.com/babe/{slug}"
    try:
        # Let any pending error-page navigation finish before we navigate away
        try:
            page.wait_for_load_state("domcontentloaded", timeout=3_000)
        except Exception:
            pass
        page.goto(url, wait_until="domcontentloaded", timeout=15_000)
        time.sleep(1.0)
        soup = BeautifulSoup(page.content(), "html.parser")
        result = _scrape_babepedia(soup)
        if not result:
            log.debug(f"      [Babepedia] No profile found for {model_name} ({url})")
        return result
    except Exception as e:
        log.debug(f"      [Babepedia] Failed for {model_name}: {e}")
        return {}


def _scrape_generic(soup: BeautifulSoup) -> dict:
    """Fallback: generic key:value extractor for unknown site layouts."""
    data = {}
    for el in soup.select("table tr, li, p"):
        text = clean(el.get_text(separator=": "))
        if re.search(r"height", text, re.I):   data.setdefault("Height",   _extract_after_colon(text))
        if re.search(r"weight", text, re.I):   data.setdefault("Weight",   _extract_after_colon(text))
        if re.search(r"measure|bust", text, re.I): data.setdefault("Measurements", _extract_after_colon(text))
        if re.search(r"^hair", text, re.I):    data.setdefault("Hair",     _extract_after_colon(text))
        if re.search(r"^eye", text, re.I):     data.setdefault("Eyes",     _extract_after_colon(text))
        if re.search(r"natural", text, re.I):  data.setdefault("Natural Breasts", _extract_after_colon(text))
        if re.search(r"tattoo", text, re.I):   data.setdefault("Tattoos",  _extract_after_colon(text))
        if re.search(r"shoe", text, re.I):     data.setdefault("Shoe Size", _extract_after_colon(text))
    return data


def _extract_after_colon(text: str) -> str:
    if ":" in text:
        return clean(text.split(":", 1)[1])
    parts = text.split(None, 1)
    return parts[1].strip() if len(parts) > 1 else ""


# ── Agency router ──────────────────────────────────────────────────────────────

AGENCY_SCRAPERS = {
    "oc models":         _scrape_oc_models,
    "hussie models":     _scrape_hussie_models,
    "nexxxt level":      _scrape_nexxxt_level,
    "foxxx modeling":    _scrape_foxxx_modeling,
    "zen models":        _scrape_zen_models,
    "101 models":        _scrape_101_models,
    "coxxx models":      _scrape_coxxx_models,
    "atmla":             _scrape_atmla,
    "the model service": _scrape_model_service,
    "east coast talent": _scrape_east_coast_talent,
    "the bakery talent": _scrape_bakery_talent,
    "invision models":   _scrape_invision_models,
    "speigler":          _scrape_spiegler_models,
}

# Profile URL templates for agencies where the URL can be derived from name slug
PROFILE_URL_TEMPLATES = {
    "oc models":         "https://ocmodeling.com/model/{slug}/",
    "hussie models":     "https://hussiemodels.com/model/{slug}",
    "nexxxt level":      "https://nexxxtleveltalentagency.com/models/{slug}/",
    "foxxx modeling":    "https://foxxxmodeling.com/model-stats-profile-page/{slug}",
    "zen models":        "https://zenmodels.org/our-models/{slug}/",
    "coxxx models":      "https://coxxxmodels.com/portfolio/{slug}",
    "atmla":             "https://atmla.com/performers/female-models/{slug}/",
    "the model service": "https://themodelservice.com/model/{slug}.html",
    "east coast talent": "https://eastcoasttalents.com/talent/{slug}/",
    "the bakery talent": "https://thebakerytalent.com/{slug}",
    "invision models":   "https://invisionmodels.com/{slug}",
    # Spiegler uses first-name-only static pages: /html/{firstname}.html
    "speigler":          "https://spieglergirls.com/html/{first}.html",
    # 101 Models uses numeric t_id URLs — handled via _101_id_map in build_profile_url()
}


def build_profile_url(agency_name: str, model_name: str) -> str:
    key = agency_name.lower().strip()
    if key == "101 models":
        # URLs use a numeric t_id populated by load_101_models_id_map()
        t_id = _101_id_map.get(model_name.lower().strip())
        if t_id:
            return (f"https://101modeling.com/site/talent/view.php"
                    f"?t_id={t_id}&pageType=profile")
        return ""
    template = PROFILE_URL_TEMPLATES.get(key)
    if not template:
        return ""
    slug = name_to_slug(model_name)
    first = name_to_slug(model_name.strip().split()[0])  # first name only for Spiegler
    return template.format(slug=slug, first=first)


# ── Sheet helpers ──────────────────────────────────────────────────────────────

def get_col_map(sheet) -> dict:
    headers = sheet.row_values(HEADER_ROW)
    return {str(h).strip(): i + 1 for i, h in enumerate(headers)}  # 1-indexed


def get_all_models(sheet, col_map: dict) -> list:
    name_col = col_map.get("Name", 1)
    last_row = sheet.get_all_values()
    models = []
    for i, row in enumerate(last_row[DATA_START_ROW - 1:], start=DATA_START_ROW):
        if len(row) < name_col:
            continue
        name = str(row[name_col - 1]).strip()
        if not name:
            continue
        # A row is considered "done" only if it has SOME profile data AND
        # specifically has Age filled (Age was added later, so rows without it
        # should be re-scraped even if other fields are present).
        def _filled(field):
            c = col_map.get(field)
            return bool(c and len(row) >= c and row[c - 1].strip())

        has_any  = any(_filled(f) for f in PROFILE_FIELDS)
        has_age  = _filled("Age")
        has_data = has_any and has_age
        models.append({"name": name, "row": i, "has_data": has_data})
    return models


# ── Core scraping ──────────────────────────────────────────────────────────────

def scrape_profile_page(page, url: str, agency_name: str, model_name: str) -> dict:
    """Load a profile page and extract stats using the site-specific scraper."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20_000)
    except Exception as te:
        err_str = str(te).lower()
        if "timeout" in err_str or "timed out" in err_str:
            log.warning(f"    [{agency_name}] Page load timed out for {model_name} — trying partial content")
        else:
            log.debug(f"    Failed to scrape {model_name} ({url}): {te}")
            return {}
    try:
        # Wix / Elementor JS sites need extra time for stats content to render
        key_for_sleep = agency_name.lower().strip()
        if key_for_sleep == "foxxx modeling":
            time.sleep(3.5)
        elif key_for_sleep == "coxxx models":
            time.sleep(5.0)   # Elementor dynamic fields take a few seconds
        else:
            time.sleep(1.5)
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        key = agency_name.lower().strip()
        scraper_fn = AGENCY_SCRAPERS.get(key, _scrape_generic)
        data = scraper_fn(soup)
        # Clean up empty values
        return {k: v for k, v in data.items() if v and v.strip()}
    except Exception as e:
        log.debug(f"    Failed to scrape {model_name} ({url}): {e}")
        return {}


def process_tab(sheet, agency_name: str, dry_run: bool, browser_ctx, overwrite: bool = False) -> int:
    """Scrape all models in a tab and write profile data back. Returns # updated."""
    col_map = get_col_map(sheet)

    # Check that profile columns exist
    missing_cols = [f for f in PROFILE_FIELDS if f not in col_map]
    if missing_cols:
        log.warning(f"  [{agency_name}] Missing columns: {missing_cols}. "
                    f"Run add_profile_columns.py first.")
        return 0

    models = get_all_models(sheet, col_map)
    if overwrite:
        todo = models  # re-scrape everyone
    else:
        todo = [m for m in models if not m["has_data"]]  # skip already-filled rows
    filled = [m for m in models if m["has_data"]]

    log.info(f"  {len(models)} models total — {len(filled)} already have data, "
             f"{len(todo)} to scrape")

    if not todo:
        log.info(f"  Nothing to do for {agency_name}.")
        return 0

    page = browser_ctx.new_page()

    # For 101 Models: build the name → t_id map from the talent listing page
    if agency_name.lower().strip() == "101 models":
        load_101_models_id_map(page)

    updates = []
    hyperlink_updates = []   # HYPERLINK() formulas for Name column, written USER_ENTERED
    updated_count = 0

    for m in todo:
        profile_url = build_profile_url(agency_name, m["name"])

        # ── Phase 1: Agency site ─────────────────────────────────────────────
        if not profile_url:
            log.debug(f"    No URL pattern for {m['name']} in {agency_name}")
            data = {}
        else:
            log.info(f"    Scraping: {m['name']} → {profile_url}")
            data = scrape_profile_page(page, profile_url, agency_name, m["name"])
            if data:
                log.info(f"      → Agency: {data}")

        # ── Phase 2: Babepedia gap-fill ──────────────────────────────────────
        # Only look up Babepedia for fields it can reliably provide that are
        # still missing after the agency scrape.
        missing_bp = BABEPEDIA_FIELDS - set(data.keys())
        if missing_bp:
            bp_raw = scrape_babepedia_page(page, m["name"])
            bp_filled = {k: v for k, v in bp_raw.items() if k in missing_bp and v}
            if bp_filled:
                log.info(f"      → Babepedia filled: {bp_filled}")
                data.update(bp_filled)

        if not data:
            log.info(f"      → No data extracted")
            continue

        updated_count += 1

        if not dry_run:
            for field, value in data.items():
                col_idx = col_map.get(field)
                if col_idx and value:
                    a1 = gspread.utils.rowcol_to_a1(m["row"], col_idx)
                    updates.append({"range": a1, "values": [[value]]})

            # Hyperlink: set the Name cell to =HYPERLINK(url, "Name")
            if profile_url:
                name_col_idx = col_map.get("Name")
                if name_col_idx:
                    escaped = m["name"].replace('"', '""')  # escape quotes for formula
                    a1 = gspread.utils.rowcol_to_a1(m["row"], name_col_idx)
                    hyperlink_updates.append({
                        "range": a1,
                        "values": [[f'=HYPERLINK("{profile_url}", "{escaped}")']]
                    })

        time.sleep(0.5)

    page.close()

    if updates and not dry_run:
        # Batch write stats in chunks of 50 (RAW — no formula interpretation needed)
        for i in range(0, len(updates), 50):
            chunk = updates[i:i+50]
            sheet.batch_update(chunk)
            time.sleep(2)
        log.info(f"  Wrote {len(updates)} cells for {agency_name}.")

    if hyperlink_updates and not dry_run:
        # Batch write HYPERLINK formulas (USER_ENTERED so Sheets evaluates the formula)
        for i in range(0, len(hyperlink_updates), 50):
            chunk = hyperlink_updates[i:i+50]
            sheet.batch_update(chunk, value_input_option="USER_ENTERED")
            time.sleep(2)
        log.info(f"  Set {len(hyperlink_updates)} name hyperlinks for {agency_name}.")

    return updated_count


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fill model profile stats into the booking list.")
    parser.add_argument("--tab", help="Process only one tab (exact name).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Scrape and log but do not write to sheet.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Re-scrape even models that already have data.")
    args = parser.parse_args()

    log.info(f"Connecting to Google Sheets...")
    creds = Credentials.from_service_account_file(str(SERVICE_ACCOUNT_FILE), scopes=SCOPES)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(SPREADSHEET_ID)
    log.info(f"Opened: {ss.title}\n")

    sheets = ss.worksheets()
    if args.tab:
        sheets = [s for s in sheets if s.title.lower() == args.tab.lower()]
        if not sheets:
            log.error(f"Tab '{args.tab}' not found.")
            return

    total_updated = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=USER_AGENT)

        for sheet in sheets:
            agency_name = sheet.title
            log.info(f"\n{'='*60}")
            log.info(f"Processing: {agency_name}")
            n = process_tab(sheet, agency_name, args.dry_run, ctx, args.overwrite)
            total_updated += n
            time.sleep(1)

        ctx.close()
        browser.close()

    mode = " [DRY RUN]" if args.dry_run else ""
    log.info(f"\nDone{mode}. Updated {total_updated} model(s) across all tabs.")
    log.info("Open the sheet to review the results.")


if __name__ == "__main__":
    main()
