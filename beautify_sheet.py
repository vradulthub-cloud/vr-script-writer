#!/usr/bin/env python3
"""
beautify_sheet.py
=================
Applies comprehensive smart UI formatting to the Model Booking List.

Per tab:
  1. Freeze header rows (1-3) + Name column
  2. Color-coded header row: Navy (booking) | Green (Available For) | Purple (stats) | Slate (Notes)
  3. Optimized column widths
  4. Collapsible column group for physical stats (Height → Shoe Size)
  5. CLIP overflow on Available For column
  6. Conditional formatting: red highlight on rows missing Age
  7. Alternating row shading (white / very light grey)

Usage:
    python3 /Users/andrewninn/Scripts/beautify_sheet.py
"""

import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SPREADSHEET_ID       = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADER_ROW_IDX = 2   # 0-indexed row 2  =  sheet row 3  (column headers)
DATA_START_IDX = 3   # 0-indexed row 3  =  sheet row 4  (first data row)
FREEZE_ROWS    = 1   # freeze only the header row (rows 1-2 are hidden)


# ── Colors ────────────────────────────────────────────────────────────────────

def rgb(r, g, b):
    return {"red": r / 255, "green": g / 255, "blue": b / 255}

C = {
    # Header backgrounds
    "navy":       rgb(26,  35, 126),   # booking cols header
    "green":      rgb(27,  94,  32),   # Available For header
    "purple":     rgb(74,  20, 140),   # stats cols header
    "slate":      rgb(55,  71,  79),   # Notes header
    "white":      rgb(255, 255, 255),
    # Rows
    "row_even":   rgb(243, 244, 246),  # very light grey
    "row_odd":    rgb(255, 255, 255),  # white
    # Conditional format (missing age)
    "warn_bg":    rgb(255, 235, 238),  # light red
    "warn_fg":    rgb(183,  28,  28),  # dark red
    # Rank tier colors (Rank column cell fill + text)
    "rank_great_bg":    rgb(255, 196,   0),  # vivid gold
    "rank_great_fg":    rgb( 60,  35,   0),  # dark brown text
    "rank_good_bg":     rgb( 52, 168,  83),  # Google green
    "rank_good_fg":     rgb(255, 255, 255),  # white text
    "rank_moderate_bg": rgb( 66, 133, 244),  # Google blue
    "rank_moderate_fg": rgb(255, 255, 255),  # white text
    "rank_unknown_bg":  rgb(200, 200, 200),  # light grey
    "rank_unknown_fg":  rgb( 80,  80,  80),  # dark grey text
}


# ── Column metadata ───────────────────────────────────────────────────────────

# Header text → preferred pixel width
COL_WIDTHS = {
    "Name":            195,
    "Age":              44,
    "AVG Rate":         82,
    "Rank":             92,
    "Location":         72,
    "Available For":   290,
    "Height":           72,
    "Weight":           62,
    "Measurements":    108,
    "Hair":             78,
    "Eyes":             68,
    "Natural Breasts":  98,
    "Tattoos":          72,
    "Shoe Size":        70,
    "Notes":           275,
    # Platform stats (collapsible group)
    "SLR Followers":    88,
    "SLR Scenes":       72,
    "SLR Views":        78,
    "VRP Followers":    88,
    "VRP Views":        80,
    "POVR Views":       80,
    "OnlyFans":         78,
    "Twitter":          72,
    "Instagram":        78,
    "SLR Profile":      88,
    "VRP Profile":      88,
}

# Categories drive header color
SKIP_TABS      = {'📋 Legend', '🔍 Search', 'Export', '📊 Dashboard'}

BOOKING_COLS   = {"Name", "Age", "AVG Rate", "Rank", "Location"}
AVAIL_COLS     = {"Available For"}
STATS_COLS     = {"Height", "Weight", "Measurements", "Hair", "Eyes",
                  "Natural Breasts", "Tattoos", "Shoe Size"}
PLATFORM_COLS  = {"SLR Followers", "SLR Scenes", "SLR Views",
                  "VRP Followers", "VRP Views", "POVR Views",
                  "OnlyFans", "Twitter", "Instagram",
                  "SLR Profile", "VRP Profile"}
NOTES_COLS     = {"Notes"}


# ── Auth / service ────────────────────────────────────────────────────────────

def get_service():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def get_all_sheets(service):
    meta = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    return meta["sheets"]


def get_headers(service, sheet_title):
    """Read row 3 (HEADER_ROW_IDX) from the given tab, return list of strings."""
    rng = f"'{sheet_title}'!1:3"
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=rng
    ).execute()
    rows = result.get("values", [])
    if len(rows) < 3:
        return []
    # Row 3 headers (0-indexed row 2)
    return [str(h).strip() for h in rows[2]]


def build_col_map(headers):
    """header name → 0-based column index"""
    return {h: i for i, h in enumerate(headers) if h}


# ── Request builders ──────────────────────────────────────────────────────────

def req_freeze(sheet_id):
    # Only freeze rows — row 1 is merged across all columns, so column freeze is not possible
    return {
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {
                    "frozenRowCount": FREEZE_ROWS,
                },
            },
            "fields": "gridProperties.frozenRowCount",
        }
    }


def req_header_colors(sheet_id, col_map):
    """Color each header cell in row 3 according to its category."""
    requests = []
    for col_name, col_idx in col_map.items():
        if col_name in BOOKING_COLS:
            bg = C["navy"]
        elif col_name in AVAIL_COLS:
            bg = C["green"]
        elif col_name in STATS_COLS or col_name in PLATFORM_COLS:
            bg = C["purple"]
        elif col_name in NOTES_COLS:
            bg = C["slate"]
        else:
            continue  # leave other cols unchanged

        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": HEADER_ROW_IDX,
                    "endRowIndex":   HEADER_ROW_IDX + 1,
                    "startColumnIndex": col_idx,
                    "endColumnIndex":   col_idx + 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": bg,
                        "textFormat": {
                            "foregroundColor": C["white"],
                            "bold": True,
                            "fontSize": 10,
                        },
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
            }
        })
    return requests


def req_col_widths(sheet_id, col_map):
    requests = []
    for col_name, width in COL_WIDTHS.items():
        if col_name not in col_map:
            continue
        col_idx = col_map[col_name]
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": col_idx,
                    "endIndex":   col_idx + 1,
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize",
            }
        })
    return requests


def req_clip_all_data_cells(sheet_id, col_map):
    """Clip overflow on ALL data cells and set font size to 9 for compactness."""
    if not col_map:
        return []
    last_col = max(col_map.values()) + 1
    return [{
        "repeatCell": {
            "range": {
                "sheetId":          sheet_id,
                "startRowIndex":    DATA_START_IDX,
                "endRowIndex":      1000,
                "startColumnIndex": 0,
                "endColumnIndex":   last_col,
            },
            "cell": {
                "userEnteredFormat": {
                    "wrapStrategy": "CLIP",
                    "textFormat": {"fontSize": 9},
                }
            },
            "fields": "userEnteredFormat(wrapStrategy,textFormat.fontSize)",
        }
    }]


def req_stats_groups(sheet_id, col_map):
    """
    One collapsed group spanning all stat columns (physical + platform).
    SLR Profile and VRP Profile are excluded — they stay visible as link anchors.
    """
    grouped_cols = (STATS_COLS | PLATFORM_COLS) - {"SLR Profile", "VRP Profile"}
    indices = sorted(col_map[c] for c in grouped_cols if c in col_map)
    if not indices:
        return []
    grp_range = {
        "sheetId":    sheet_id,
        "dimension":  "COLUMNS",
        "startIndex": indices[0],
        "endIndex":   indices[-1] + 1,
    }
    return [
        {"addDimensionGroup": {"range": grp_range}},
        {
            "updateDimensionGroup": {
                "dimensionGroup": {
                    "range":     grp_range,
                    "depth":     1,
                    "collapsed": True,
                },
                "fields": "collapsed",
            }
        },
    ]


def req_delete_all_column_groups(sheet_data):
    """Delete ALL existing column groups for this sheet using their actual ranges."""
    requests = []
    for group in sheet_data.get("columnGroups", []):
        requests.append({"deleteDimensionGroup": {"range": group["range"]}})
    return requests


def col_letter(idx: int) -> str:
    """0-based column index → A1 letter (e.g. 0→A, 25→Z, 26→AA)."""
    result = ""
    n = idx + 1
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def req_age_flags(sheet_id, col_map):
    """
    Color-code rows for models under 20:
      Age 18          → bright red   (absolute no-go)
      Age 19, no platform data → orange (no verified scenes)
      Age 19, has SLR/VRP/POVR data  → amber  (possible exception — review)
    """
    if "Age" not in col_map:
        return []

    age_col  = col_letter(col_map["Age"])
    slr_col  = col_letter(col_map["SLR Followers"]) if "SLR Followers" in col_map else None
    vrp_col  = col_letter(col_map["VRP Views"])     if "VRP Views"     in col_map else None
    povr_col = col_letter(col_map["POVR Views"])    if "POVR Views"    in col_map else None

    first_row = DATA_START_IDX + 1   # 1-indexed first data row
    last_col  = max(col_map.values()) + 1

    row_range = {
        "sheetId":          sheet_id,
        "startRowIndex":    DATA_START_IDX,
        "endRowIndex":      1000,
        "startColumnIndex": 0,
        "endColumnIndex":   last_col,
    }

    # Build platform-has-data expression
    platform_parts = [f'${c}{first_row}<>""' for c in [slr_col, vrp_col, povr_col] if c]
    has_platform = "OR(" + ",".join(platform_parts) + ")" if platform_parts else "FALSE"

    # Use VALUE() so text-stored ages ("18", "19") match numeric comparison
    rules = [
        # Age 18 — absolute no-go — bright red
        (
            f'=VALUE(${age_col}{first_row})=18',
            rgb(229, 57, 53),   # red 600
            rgb(255, 255, 255),
        ),
        # Age 19, no platform data — orange warning
        (
            f'=AND(VALUE(${age_col}{first_row})=19,NOT({has_platform}))',
            rgb(245, 124, 0),   # orange 800
            rgb(255, 255, 255),
        ),
        # Age 19, has platform data — amber (review carefully)
        (
            f'=AND(VALUE(${age_col}{first_row})=19,{has_platform})',
            rgb(251, 192, 45),  # amber 400
            rgb(60,  40,   0),  # dark brown text
        ),
    ]

    requests = []
    for idx, (formula, bg, fg) in enumerate(rules):
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [row_range],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": formula}],
                        },
                        "format": {
                            "backgroundColor": bg,
                            "textFormat": {"foregroundColor": fg, "bold": True},
                        },
                    },
                },
                "index": idx,
            }
        })
    return requests


def req_conditional_missing_age(sheet_id, col_map):
    """Highlight entire row in soft red when Age is empty."""
    if "Age" not in col_map:
        return []
    age_idx  = col_map["Age"]
    age_col  = chr(ord("A") + age_idx)   # works for cols A-Z
    formula  = f'=${age_col}{DATA_START_IDX + 1}=""'
    last_col = max(col_map.values()) + 1

    return [{
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{
                    "sheetId":          sheet_id,
                    "startRowIndex":    DATA_START_IDX,
                    "endRowIndex":      1000,
                    "startColumnIndex": 0,
                    "endColumnIndex":   last_col,
                }],
                "booleanRule": {
                    "condition": {
                        "type": "CUSTOM_FORMULA",
                        "values": [{"userEnteredValue": formula}],
                    },
                    "format": {
                        "backgroundColor": C["warn_bg"],
                        "textFormat": {"foregroundColor": C["warn_fg"]},
                    },
                },
            },
            "index": 0,
        }
    }]


def req_delete_conditional_rules(sheet_id, sheet_data):
    """Delete ALL existing conditional format rules for this sheet."""
    requests = []
    rules = sheet_data.get("conditionalFormats", [])
    # Delete in reverse order (highest index first) to avoid index drift
    for i in range(len(rules) - 1, -1, -1):
        requests.append({
            "deleteConditionalFormatRule": {
                "sheetId": sheet_id,
                "index": i,
            }
        })
    return requests


def req_rank_colors(sheet_id, col_map):
    """
    Add conditional format rules so each Rank cell is color-coded:
      Great    → vivid gold bg + dark text + bold
      Good     → green bg + white text + bold
      Moderate → blue bg + white text + bold
      Unknown  → grey bg + dark grey text
    """
    if "Rank" not in col_map:
        return []

    rank_idx = col_map["Rank"]
    cell_range = {
        "sheetId":          sheet_id,
        "startRowIndex":    DATA_START_IDX,
        "endRowIndex":      1000,
        "startColumnIndex": rank_idx,
        "endColumnIndex":   rank_idx + 1,
    }

    tiers = [
        ("Great",    C["rank_great_bg"],    C["rank_great_fg"]),
        ("Good",     C["rank_good_bg"],     C["rank_good_fg"]),
        ("Moderate", C["rank_moderate_bg"], C["rank_moderate_fg"]),
        ("Unknown",  C["rank_unknown_bg"],  C["rank_unknown_fg"]),
    ]

    requests = []
    for idx, (tier, bg, fg) in enumerate(tiers):
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [cell_range],
                    "booleanRule": {
                        "condition": {
                            "type": "TEXT_EQ",
                            "values": [{"userEnteredValue": tier}],
                        },
                        "format": {
                            "backgroundColor": bg,
                            "textFormat": {
                                "foregroundColor": fg,
                                "bold": tier != "Unknown",
                            },
                        },
                    },
                },
                "index": idx,
            }
        })
    return requests


def req_banding(sheet_id, col_map):
    """Alternating row shading for data rows."""
    if not col_map:
        return []
    last_col = max(col_map.values()) + 1
    return [{
        "addBanding": {
            "bandedRange": {
                "range": {
                    "sheetId":          sheet_id,
                    "startRowIndex":    DATA_START_IDX,
                    "endRowIndex":      1000,
                    "startColumnIndex": 0,
                    "endColumnIndex":   last_col,
                },
                "rowProperties": {
                    "headerColor":     C["row_odd"],
                    "firstBandColor":  C["row_odd"],
                    "secondBandColor": C["row_even"],
                },
            }
        }
    }]


def req_delete_existing_bandings(sheet_data):
    """Delete all existing banded ranges so we don't duplicate."""
    requests = []
    for br in sheet_data.get("bandedRanges", []):
        requests.append({
            "deleteBanding": {"bandedRangeId": br["bandedRangeId"]}
        })
    return requests


def req_row_height(sheet_id):
    """Set data row height to 20px — maximum compactness."""
    return [{
        "updateDimensionProperties": {
            "range": {
                "sheetId":    sheet_id,
                "dimension":  "ROWS",
                "startIndex": DATA_START_IDX,
                "endIndex":   1000,
            },
            "properties": {"pixelSize": 20},
            "fields": "pixelSize",
        }
    }]


def req_basic_filter(sheet_id, col_map):
    """Native ▼ filter arrows on every header cell."""
    if not col_map:
        return []
    last_col = max(col_map.values()) + 1
    return [{
        "setBasicFilter": {
            "filter": {
                "range": {
                    "sheetId":          sheet_id,
                    "startRowIndex":    HEADER_ROW_IDX,
                    "endRowIndex":      1000,
                    "startColumnIndex": 0,
                    "endColumnIndex":   last_col,
                }
            }
        }
    }]


def req_slicers(sheet_id, col_map):
    """
    One slicer per filterable column, each anchored directly at that column's
    header cell so it appears right next to the column name.
    """
    slicer_cols = [
        ("Age",          COL_WIDTHS.get("Age",          80)),
        ("Location",     COL_WIDTHS.get("Location",     120)),
        ("AVG Rate",     COL_WIDTHS.get("AVG Rate",     100)),
        ("Rank",         COL_WIDTHS.get("Rank",         100)),
        ("Last Booked Date", 140),
    ]
    requests = []
    for col_name, width in slicer_cols:
        if col_name not in col_map:
            continue
        col_idx = col_map[col_name]
        requests.append({
            "addSlicer": {
                "slicer": {
                    "spec": {
                        "dataRange": {
                            "sheetId":          sheet_id,
                            "startRowIndex":    HEADER_ROW_IDX,
                            "endRowIndex":      1000,
                            "startColumnIndex": 0,
                            "endColumnIndex":   max(col_map.values()) + 1,
                        },
                        "columnIndex": col_idx,
                        "title":       col_name,
                        "textFormat":  {"fontSize": 9},
                    },
                    "position": {
                        "overlayPosition": {
                            "anchorCell": {
                                "sheetId":     sheet_id,
                                "rowIndex":    HEADER_ROW_IDX,   # sits on the header row
                                "columnIndex": col_idx,           # at its own column
                            },
                            "offsetXPixels": 0,
                            "offsetYPixels": 0,
                            "widthPixels":   max(width, 100),
                            "heightPixels":  56,
                        }
                    },
                }
            }
        })
    return requests



def req_booked_indicator(sheet_id, col_map):
    """
    Bold + subtle teal tint on rows where we've personally booked the model.
    Applied at low priority so age-warning colors still override.
    """
    col_name = "Last Booked Date" if "Last Booked Date" in col_map else "Dates Booked"
    if col_name not in col_map:
        return []
    booked_col  = col_letter(col_map[col_name])
    first_row   = DATA_START_IDX + 1
    last_col    = max(col_map.values()) + 1
    formula     = f'=${booked_col}{first_row}<>""'
    return [{
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{
                    "sheetId":          sheet_id,
                    "startRowIndex":    DATA_START_IDX,
                    "endRowIndex":      1000,
                    "startColumnIndex": 0,
                    "endColumnIndex":   last_col,
                }],
                "booleanRule": {
                    "condition": {
                        "type":   "CUSTOM_FORMULA",
                        "values": [{"userEnteredValue": formula}],
                    },
                    "format": {
                        "backgroundColor": rgb(224, 247, 250),   # very light teal
                        "textFormat": {"bold": True},
                    },
                },
            },
            "index": 99,   # low priority — age/rank colors override
        }
    }]


NEGATIVE_NOTE_KEYWORDS = [
    "bad attitude", "unpredictable", "moody", "not fun to work with",
    "inability to take direction", "doesnt take direction",
    "doesn't take direction", "struggles", "gained weight", "not fun",
]


def req_negative_notes_flag(sheet_id, col_map):
    """
    Flag rows where Notes contain attitude / on-set problems.
    Adds a gold/amber left border effect (distinct from age colors).
    """
    if "Notes" not in col_map:
        return []
    notes_col = col_letter(col_map["Notes"])
    first_row = DATA_START_IDX + 1
    last_col  = max(col_map.values()) + 1

    # Build OR(ISNUMBER(SEARCH(...)), ...) formula
    search_parts = [
        f'ISNUMBER(SEARCH("{kw}",LOWER(${notes_col}{first_row})))'
        for kw in NEGATIVE_NOTE_KEYWORDS
    ]
    formula = "=OR(" + ",".join(search_parts) + ")"

    return [{
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{
                    "sheetId":          sheet_id,
                    "startRowIndex":    DATA_START_IDX,
                    "endRowIndex":      1000,
                    "startColumnIndex": 0,
                    "endColumnIndex":   last_col,
                }],
                "booleanRule": {
                    "condition": {
                        "type":   "CUSTOM_FORMULA",
                        "values": [{"userEnteredValue": formula}],
                    },
                    "format": {
                        "backgroundColor": rgb(255, 243, 224),   # light amber — caution
                        "textFormat": {"foregroundColor": rgb(230, 81, 0)},
                    },
                },
            },
            "index": 98,   # below age colors (0-2), above banded rows
        }
    }]


def req_sort_by_recency(sheet_id, col_map):
    """Sort data rows by Last Booked Date DESC — most recently booked models first."""
    col_name = "Last Booked Date" if "Last Booked Date" in col_map else "Dates Booked"
    if col_name not in col_map:
        return []
    return [{
        "sortRange": {
            "range": {
                "sheetId":          sheet_id,
                "startRowIndex":    DATA_START_IDX,
                "endRowIndex":      1000,
                "startColumnIndex": 0,
                "endColumnIndex":   max(col_map.values()) + 1,
            },
            "sortSpecs": [{
                "dimensionIndex": col_map[col_name],
                "sortOrder":      "DESCENDING",
            }],
        }
    }]


def req_hide_title_rows(sheet_id):
    """Hide rows 1 and 2 (agency name / website) so header row is first visible."""
    return [{
        "updateDimensionProperties": {
            "range": {
                "sheetId":    sheet_id,
                "dimension":  "ROWS",
                "startIndex": 0,   # row 1
                "endIndex":   2,   # through row 2 (exclusive)
            },
            "properties": {"hiddenByUser": True},
            "fields": "hiddenByUser",
        }
    }]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    service = get_service()
    sheets  = get_all_sheets(service)

    # Fetch full sheet metadata (includes banded ranges) for cleanup
    full_meta = service.spreadsheets().get(
        spreadsheetId=SPREADSHEET_ID
    ).execute()
    sheet_meta_by_id = {s["properties"]["sheetId"]: s for s in full_meta["sheets"]}

    cleanup_requests = []
    format_requests  = []

    for sheet in sheets:
        props      = sheet["properties"]
        sheet_id   = props["sheetId"]
        sheet_name = props["title"]

        if sheet_name in SKIP_TABS:
            print(f"  [SKIP] {sheet_name}: non-agency tab")
            continue

        headers = get_headers(service, sheet_name)
        if not headers:
            print(f"  [SKIP] {sheet_name}: no headers found")
            continue

        col_map = build_col_map(headers)
        print(f"  [OK]   {sheet_name}: {len(col_map)} columns")

        sheet_data = sheet_meta_by_id.get(sheet_id, {})

        # Phase 1 cleanup: delete all existing groups, bandings, conditional rules, slicers
        cleanup_requests += req_delete_all_column_groups(sheet_data)
        cleanup_requests += req_delete_existing_bandings(sheet_data)
        cleanup_requests += req_delete_conditional_rules(sheet_id, sheet_data)

        # Phase 2 formatting
        format_requests += [req_freeze(sheet_id)]
        format_requests += req_hide_title_rows(sheet_id)
        format_requests += req_header_colors(sheet_id, col_map)
        format_requests += req_col_widths(sheet_id, col_map)
        format_requests += req_clip_all_data_cells(sheet_id, col_map)
        format_requests += req_stats_groups(sheet_id, col_map)
        format_requests += req_rank_colors(sheet_id, col_map)
        format_requests += req_age_flags(sheet_id, col_map)
        format_requests += req_negative_notes_flag(sheet_id, col_map)
        format_requests += req_booked_indicator(sheet_id, col_map)
        format_requests += req_conditional_missing_age(sheet_id, col_map)
        format_requests += req_banding(sheet_id, col_map)
        format_requests += req_row_height(sheet_id)
        format_requests += req_basic_filter(sheet_id, col_map)
        format_requests += req_sort_by_recency(sheet_id, col_map)

    all_requests = cleanup_requests + format_requests

    if not all_requests:
        print("No requests to send.")
        return

    print(f"\nSending {len(all_requests)} formatting requests...")

    # Send in chunks of 100 to avoid API limits
    chunk_size = 100
    for i in range(0, len(all_requests), chunk_size):
        chunk = all_requests[i:i + chunk_size]
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={"requests": chunk}
            ).execute()
            print(f"  Chunk {i // chunk_size + 1}: {len(chunk)} requests sent.")
        except Exception as e:
            print(f"  ERROR in chunk {i // chunk_size + 1}: {e}")

    print("\nDone! Reload the sheet to see the changes.")
    print("Stats columns (Height → Shoe Size) are now grouped — click the [-] to collapse them.")


if __name__ == "__main__":
    main()
