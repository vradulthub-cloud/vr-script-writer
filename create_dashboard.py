#!/usr/bin/env python3
"""
create_dashboard.py
===================
Creates (or refreshes) the '📊 Dashboard' tab with aggregate stats:
  - Summary KPIs: total models, active/stale counts, total bookings
  - Rank info pills bar
  - Two-column middle layout: Bookings by Agency (left) | Rank Dist + Priority Outreach (right)
  - Top 15 most-booked models
  - Stale re-book targets (booked before but 12+ months ago)
  - Models with no bookings recorded

Usage:
    python3 /Users/andrewninn/Scripts/create_dashboard.py
"""

import os
from datetime import date, timedelta
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread

SPREADSHEET_ID       = "1Dxrh0UZNqoBt6otZqsU85fxz9z-dt0csSCV9sGdobKw"
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SKIP_TABS  = {'📋 Legend', '🔍 Search', 'Export', '📊 Dashboard'}
HEADER_ROW = 2   # 0-indexed
DATA_START = 3   # 0-indexed
TAB_TITLE  = '📊 Dashboard'

TODAY      = date.today()
D90        = TODAY - timedelta(days=90)
D180       = TODAY - timedelta(days=180)
D365       = TODAY - timedelta(days=365)

# ── Colour palette ────────────────────────────────────────────────────────────
def rgb(r, g, b):
    return {"red": r/255, "green": g/255, "blue": b/255}

NAVY        = rgb(26, 35, 126)
NAVY_DARK   = rgb(13, 17, 63)
WHITE       = rgb(255, 255, 255)
TEAL        = rgb(0, 150, 136)
TEAL_LIGHT  = rgb(224, 247, 250)
PURPLE      = rgb(74, 20, 140)
PURPLE_LITE = rgb(243, 229, 245)
GREEN       = rgb(27, 94, 32)
GREEN_LITE  = rgb(232, 245, 233)
AMBER       = rgb(230, 81, 0)
AMBER_LITE  = rgb(255, 243, 224)
RED         = rgb(183, 28, 28)
RED_LITE    = rgb(255, 235, 238)
GREY_LITE   = rgb(248, 249, 250)
GREY        = rgb(200, 200, 200)
DARK        = rgb(30, 30, 30)
HEADER_BG   = rgb(55, 71, 79)


# ── Helpers ───────────────────────────────────────────────────────────────────
def sheets_date_to_py(val):
    """Parse 'Mon YYYY' text (e.g. 'Dec 2025') or a Sheets serial number to a date."""
    if not val:
        return None
    s = str(val).strip()
    # Try text format first: "Dec 2025"
    try:
        from datetime import datetime as _dt
        return _dt.strptime(s, '%b %Y').date()
    except ValueError:
        pass
    # Fall back to Sheets serial number (integer days since 1899-12-30)
    try:
        n = int(float(s))
        if n < 1:
            return None
        origin = date(1899, 12, 30)
        return origin + timedelta(days=n)
    except Exception:
        return None


def parse_bookings(val):
    """Return integer booking count from a cell value, or 0."""
    try:
        return int(float(str(val)))
    except Exception:
        return 0


def collect_data(ss):
    """Return list of dicts, one per model across all agency tabs."""
    rows = []
    for ws in ss.worksheets():
        if ws.title in SKIP_TABS:
            continue
        data = ws.get_all_values()
        if len(data) <= DATA_START:
            continue
        headers = [h.strip() for h in data[HEADER_ROW]]
        col = {h: i for i, h in enumerate(headers) if h}
        if "Name" not in col:
            continue

        name_idx    = col.get("Name", 0)
        rank_idx    = col.get("Rank")
        bookings_idx = col.get("Bookings")
        lbd_idx     = col.get("Last Booked Date")
        status_idx  = col.get("Status")
        loc_idx     = col.get("Location")

        for row in data[DATA_START:]:
            name = str(row[name_idx]).strip() if name_idx < len(row) else ""
            # Strip HYPERLINK formula if gspread returned formula text instead of display value
            import re as _re
            _m = _re.match(r'=?HYPERLINK\s*\(\s*"[^"]*"\s*,\s*"([^"]*)"\s*\)', name, _re.IGNORECASE)
            if _m:
                name = _m.group(1)
            if not name:
                continue
            rank     = str(row[rank_idx]).strip()     if rank_idx is not None and rank_idx < len(row) else ""
            bookings = parse_bookings(row[bookings_idx]) if bookings_idx is not None and bookings_idx < len(row) else 0
            lbd      = sheets_date_to_py(row[lbd_idx]) if lbd_idx is not None and lbd_idx < len(row) else None
            status   = str(row[status_idx]).strip()   if status_idx is not None and status_idx < len(row) else ""
            location = str(row[loc_idx]).strip()      if loc_idx is not None and loc_idx < len(row) else ""

            rows.append({
                "agency":    ws.title,
                "name":      name,
                "rank":      rank,
                "bookings":  bookings,
                "lbd":       lbd,
                "status":    status,
                "location":  location,
            })
    return rows


# ── Sheet helpers ─────────────────────────────────────────────────────────────
def repeat_cell(sid, r1, c1, r2, c2, fmt, fields=None):
    if fields is None:
        fields = "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)"
    return {"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "cell": {"userEnteredFormat": fmt},
        "fields": fields,
    }}


def merge(sid, r1, c1, r2, c2):
    return {"mergeCells": {
        "range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "mergeType": "MERGE_ALL",
    }}


def col_width(sid, col, px):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS",
                  "startIndex": col, "endIndex": col+1},
        "properties": {"pixelSize": px}, "fields": "pixelSize",
    }}


def row_height(sid, r1, r2, px):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS",
                  "startIndex": r1, "endIndex": r2},
        "properties": {"pixelSize": px}, "fields": "pixelSize",
    }}


def write_cell(sid, row, col, value, formula=False):
    if formula:
        val = {"formulaValue": value}
    elif isinstance(value, (int, float)):
        val = {"numberValue": value}
    else:
        val = {"stringValue": str(value)}
    return {"updateCells": {
        "rows": [{"values": [{"userEnteredValue": val}]}],
        "fields": "userEnteredValue",
        "start": {"sheetId": sid, "rowIndex": row, "columnIndex": col},
    }}


def write_row(sid, row, col_start, values):
    """Write a list of plain string/number values starting at col_start."""
    cells = []
    for v in values:
        if isinstance(v, (int, float)):
            cells.append({"userEnteredValue": {"numberValue": v}})
        elif isinstance(v, str) and v.startswith("="):
            cells.append({"userEnteredValue": {"formulaValue": v}})
        else:
            cells.append({"userEnteredValue": {"stringValue": str(v)}})
    return {"updateCells": {
        "rows": [{"values": cells}],
        "fields": "userEnteredValue",
        "start": {"sheetId": sid, "rowIndex": row, "columnIndex": col_start},
    }}


def fmt_row(sid, row, cols, bg, fg=None, bold=False, size=9,
            halign="LEFT", valign="MIDDLE"):
    f = {
        "backgroundColor": bg,
        "textFormat": {
            "foregroundColor": fg or DARK,
            "bold": bold,
            "fontSize": size,
        },
        "horizontalAlignment": halign,
        "verticalAlignment": valign,
    }
    return repeat_cell(sid, row, 0, row+1, cols, f)


def section_header(sid, row, col_start, col_end, text):
    """Bold section divider row — 28px tall."""
    reqs = [
        merge(sid, row, col_start, row+1, col_end),
        write_cell(sid, row, col_start, " " + text),
        repeat_cell(sid, row, col_start, row+1, col_end, {
            "backgroundColor": HEADER_BG,
            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 10},
            "horizontalAlignment": "LEFT",
            "verticalAlignment": "MIDDLE",
        }),
        row_height(sid, row, row+1, 28),
    ]
    return reqs


def kpi_block(sid, row, col, label, value, bg, fg):
    """Write a KPI card: label in row, value in row+1."""
    return [
        write_cell(sid, row,   col, label),
        write_cell(sid, row+1, col, value if isinstance(value, (int, float)) else str(value)),
        repeat_cell(sid, row,   col, row+1,   col+2, {
            "backgroundColor": bg,
            "textFormat": {"foregroundColor": fg, "bold": True, "fontSize": 9},
            "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
        }),
        repeat_cell(sid, row+1, col, row+2, col+2, {
            "backgroundColor": bg,
            "textFormat": {"foregroundColor": fg, "bold": True, "fontSize": 20},
            "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
        }),
        merge(sid, row,   col, row+1,   col+2),
        merge(sid, row+1, col, row+2,   col+2),
        row_height(sid, row,   row+1, 20),
        row_height(sid, row+1, row+2, 44),
    ]


def rank_badge_cell(sid, row, col, rank):
    """Apply rank-specific background and white text to a single cell."""
    rank_bg = {
        "Great":    rgb(27, 94, 32),
        "Good":     rgb(0, 121, 107),
        "Moderate": rgb(230, 81, 0),
        "Unknown":  rgb(97, 97, 97),
        "Poor":     rgb(183, 28, 28),
        "Elite":    rgb(26, 35, 126),
    }
    bg = rank_bg.get(rank, rgb(97, 97, 97))
    return repeat_cell(sid, row, col, row+1, col+1, {
        "backgroundColor": bg,
        "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
    })


def recency_cell(sid, row, col, lbd):
    """Color a Last Booked cell based on recency."""
    if lbd is None:
        bg = rgb(224, 224, 224)   # light grey — never booked
    elif lbd >= D90:
        bg = rgb(200, 230, 201)   # light green — within 90 days
    elif lbd >= D365:
        bg = rgb(255, 224, 178)   # light amber — 90-365 days
    else:
        bg = rgb(255, 205, 210)   # light red — 12+ months
    return repeat_cell(sid, row, col, row+1, col+1, {
        "backgroundColor": bg,
        "textFormat": {"foregroundColor": DARK, "bold": False, "fontSize": 9},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
    })


def send(service, requests):
    chunk = 50
    for i in range(0, len(requests), chunk):
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"requests": requests[i:i+chunk]}
        ).execute()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    creds   = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc      = gspread.authorize(creds)
    service = build("sheets", "v4", credentials=creds)
    ss      = gc.open_by_key(SPREADSHEET_ID)

    # ── Gather data ───────────────────────────────────────────────────────────
    print("Gathering data from all agency tabs…")
    models = collect_data(ss)
    print(f"  {len(models)} models loaded from {len({m['agency'] for m in models})} agencies.")

    total        = len(models)
    total_bk     = sum(m["bookings"] for m in models)
    booked_any   = [m for m in models if m["bookings"] > 0]
    stale        = [m for m in models if m["lbd"] and m["lbd"] < D365]
    recent_90    = [m for m in models if m["lbd"] and m["lbd"] >= D90]
    recent_180   = [m for m in models if m["lbd"] and m["lbd"] >= D180]
    unbooked     = [m for m in models if m["bookings"] == 0]

    # Agency booking summary
    agency_stats = {}
    for m in models:
        a = m["agency"]
        if a not in agency_stats:
            agency_stats[a] = {"models": 0, "bookings": 0}
        agency_stats[a]["models"]   += 1
        agency_stats[a]["bookings"] += m["bookings"]
    agency_rows = sorted(agency_stats.items(), key=lambda x: -x[1]["bookings"])

    # Rank distribution
    rank_counts = {}
    for m in models:
        r = m["rank"] or "Unknown"
        rank_counts[r] = rank_counts.get(r, 0) + 1
    rank_order = ["Elite", "Great", "Good", "Moderate", "Poor", "Unknown"]
    rank_rows = [(r, rank_counts.get(r, 0)) for r in rank_order if rank_counts.get(r, 0) > 0]
    for r, c in sorted(rank_counts.items(), key=lambda x: -x[1]):
        if r not in rank_order:
            rank_rows.append((r, c))

    # Top 15 most-booked
    top15 = sorted(booked_any, key=lambda x: -x["bookings"])[:15]

    # Pills bar data
    great_count    = sum(1 for m in models if m["rank"] == "Great")
    good_count     = sum(1 for m in models if m["rank"] == "Good")
    moderate_count = sum(1 for m in models if m["rank"] == "Moderate")
    unknown_count  = sum(1 for m in models if m["rank"] not in ("Great", "Good", "Moderate", "Elite", "Poor"))
    avg_bk         = round(total_bk / total, 1) if total else 0
    top_agency     = agency_rows[0][0] if agency_rows else "—"

    # Priority outreach: Great/Good not booked in 6+ months
    hot_targets = [m for m in models
                   if m["rank"] in ("Great", "Good")
                   and (m["lbd"] is None or m["lbd"] < D180)]
    rank_order_hot = {"Great": 0, "Good": 1}
    hot_targets.sort(key=lambda x: (rank_order_hot.get(x["rank"], 2), x["lbd"] or date.min))
    hot_targets = hot_targets[:10]

    # ── Get or create tab ─────────────────────────────────────────────────────
    existing = {ws.title: ws for ws in ss.worksheets()}
    if TAB_TITLE in existing:
        ws = existing[TAB_TITLE]
        ws.clear()
        ws.resize(rows=600, cols=14)
        print(f"Cleared existing '{TAB_TITLE}' tab.")
    else:
        ws = ss.add_worksheet(title=TAB_TITLE, rows=600, cols=14)
        print(f"Created '{TAB_TITLE}' tab.")

    sid = ws.id

    # Move to position 2 (after Legend and Search)
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{"updateSheetProperties": {
            "properties": {"sheetId": sid, "index": 2},
            "fields": "index",
        }}]}
    ).execute()

    # ── Build all requests ────────────────────────────────────────────────────
    reqs = []
    NUM_COLS = 14

    # Unmerge all cells first — ws.clear() removes values but not merge state,
    # which causes old merged ranges to silently block new cell writes.
    reqs.append({"unmergeCells": {
        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 600,
                  "startColumnIndex": 0, "endColumnIndex": NUM_COLS},
    }})

    # Column widths — col 2 wide for agency names (full-width tables)
    # col 8 wide for agency names in Priority Outreach (right panel)
    # Total ~950px so all 6 KPI cards fit comfortably in viewport
    widths = [150, 45, 115, 55, 58, 78, 15, 110, 92, 58, 58, 58, 42, 15]
    for i, px in enumerate(widths):
        reqs.append(col_width(sid, i, px))

    # ── Title bar row 0 ───────────────────────────────────────────────────────
    reqs += [
        row_height(sid, 0, 1, 40),
        merge(sid, 0, 0, 1, NUM_COLS),
        write_cell(sid, 0, 0, "📊  BOOKING DASHBOARD"),
        repeat_cell(sid, 0, 0, 1, NUM_COLS, {
            "backgroundColor": NAVY,
            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 14},
            "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
        }),
    ]

    # Subtitle row 1
    reqs += [
        row_height(sid, 1, 2, 18),
        merge(sid, 1, 0, 2, NUM_COLS),
        write_cell(sid, 1, 0, f"Last refreshed: {TODAY.strftime('%B %d, %Y')}  —  Run create_dashboard.py to update"),
        repeat_cell(sid, 1, 0, 2, NUM_COLS, {
            "backgroundColor": NAVY_DARK,
            "textFormat": {"foregroundColor": rgb(180,190,220), "bold": False, "fontSize": 8},
            "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
        }),
    ]

    # Spacer row 2
    reqs.append(row_height(sid, 2, 3, 8))

    # ── KPI rows (rows 3-4) ───────────────────────────────────────────────────
    kpis = [
        (0,  "TOTAL MODELS",     total,          TEAL,        WHITE),
        (2,  "TOTAL BOOKINGS",   total_bk,        NAVY,        WHITE),
        (4,  "BOOKED 90 DAYS",   len(recent_90),  GREEN,       WHITE),
        (6,  "BOOKED 180 DAYS",  len(recent_180), rgb(46,125,50), WHITE),
        (8,  "STALE (12+ MO)",   len(stale),      AMBER,       WHITE),
        (10, "NEVER BOOKED",     len(unbooked),   RED,         WHITE),
    ]
    for col, label, val, bg, fg in kpis:
        reqs += kpi_block(sid, 3, col, label, val, bg, fg)

    # Spacer row 5
    reqs.append(row_height(sid, 5, 6, 8))

    # ── Row 6: Rank pills bar ─────────────────────────────────────────────────
    pills_row = 6
    reqs.append(row_height(sid, pills_row, pills_row+1, 22))

    # GREAT pill — cols 0-1
    reqs += [
        merge(sid, pills_row, 0, pills_row+1, 2),
        write_cell(sid, pills_row, 0, f"GREAT   {great_count}"),
        repeat_cell(sid, pills_row, 0, pills_row+1, 2, {
            "backgroundColor": rgb(27, 94, 32),
            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9},
            "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
        }),
    ]

    # GOOD pill — cols 2-3
    reqs += [
        merge(sid, pills_row, 2, pills_row+1, 4),
        write_cell(sid, pills_row, 2, f"GOOD   {good_count}"),
        repeat_cell(sid, pills_row, 2, pills_row+1, 4, {
            "backgroundColor": rgb(0, 121, 107),
            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9},
            "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
        }),
    ]

    # MODERATE pill — cols 4-5
    reqs += [
        merge(sid, pills_row, 4, pills_row+1, 6),
        write_cell(sid, pills_row, 4, f"MODERATE   {moderate_count}"),
        repeat_cell(sid, pills_row, 4, pills_row+1, 6, {
            "backgroundColor": rgb(230, 81, 0),
            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9},
            "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
        }),
    ]

    # UNKNOWN pill — cols 6-7
    reqs += [
        merge(sid, pills_row, 6, pills_row+1, 8),
        write_cell(sid, pills_row, 6, f"UNKNOWN   {unknown_count}"),
        repeat_cell(sid, pills_row, 6, pills_row+1, 8, {
            "backgroundColor": rgb(97, 97, 97),
            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9},
            "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
        }),
    ]

    # AVG BK/MODEL pill — cols 8-9
    reqs += [
        merge(sid, pills_row, 8, pills_row+1, 10),
        write_cell(sid, pills_row, 8, f"AVG BK/MODEL   {avg_bk}"),
        repeat_cell(sid, pills_row, 8, pills_row+1, 10, {
            "backgroundColor": NAVY,
            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9},
            "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
        }),
    ]

    # TOP AGENCY pill — cols 10-13
    reqs += [
        merge(sid, pills_row, 10, pills_row+1, 14),
        write_cell(sid, pills_row, 10, f"TOP AGENCY   {top_agency}"),
        repeat_cell(sid, pills_row, 10, pills_row+1, 14, {
            "backgroundColor": rgb(74, 20, 140),
            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9},
            "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
        }),
    ]

    # Spacer row 7
    reqs.append(row_height(sid, 7, 8, 12))

    # ── Two-column layout starts at row 8 ─────────────────────────────────────
    TWO_COL_START = 8
    lr = TWO_COL_START   # left cursor
    rr = TWO_COL_START   # right cursor

    # Max agency bookings for bar chart
    max_agency_bk = agency_rows[0][1]["bookings"] if agency_rows else 1

    # ── LEFT: BOOKINGS BY AGENCY (cols 0-5) ───────────────────────────────────
    # Section header
    reqs += [
        merge(sid, lr, 0, lr+1, 6),
        write_cell(sid, lr, 0, " 📋 BOOKINGS BY AGENCY"),
        repeat_cell(sid, lr, 0, lr+1, 6, {
            "backgroundColor": HEADER_BG,
            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 10},
            "horizontalAlignment": "LEFT", "verticalAlignment": "MIDDLE",
        }),
        row_height(sid, lr, lr+1, 28),
    ]
    lr += 1

    # Column headers: Agency | Models | Bookings | Avg | % | Bar
    reqs.append(write_row(sid, lr, 0, ["Agency", "Models", "Bookings", "Avg", "%", "Bar"]))
    reqs.append(repeat_cell(sid, lr, 0, lr+1, 6, {
        "backgroundColor": HEADER_BG,
        "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9},
        "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
    }))
    reqs.append(row_height(sid, lr, lr+1, 20))
    lr += 1

    for i, (agency, stats) in enumerate(agency_rows):
        m_cnt = stats["models"]
        b_cnt = stats["bookings"]
        avg   = round(b_cnt / m_cnt, 1) if m_cnt else 0
        pct   = f"{round(b_cnt/total_bk*100, 1)}%" if total_bk else "0%"
        # Unicode bar: 8 chars wide, relative to max
        filled = round((b_cnt / max_agency_bk) * 8) if max_agency_bk else 0
        bar = "▓" * filled + "░" * (8 - filled)
        bg  = WHITE if i % 2 == 0 else GREY_LITE
        reqs.append(write_row(sid, lr, 0, [agency, m_cnt, b_cnt, avg, pct, bar]))
        reqs.append(repeat_cell(sid, lr, 0, lr+1, 6, {
            "backgroundColor": bg,
            "textFormat": {"foregroundColor": DARK, "bold": False, "fontSize": 9},
            "horizontalAlignment": "LEFT", "verticalAlignment": "MIDDLE",
        }))
        # Right-align numeric columns
        reqs.append(repeat_cell(sid, lr, 1, lr+1, 5, {
            "backgroundColor": bg,
            "textFormat": {"foregroundColor": DARK, "bold": False, "fontSize": 9},
            "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
        }))
        reqs.append(row_height(sid, lr, lr+1, 18))
        lr += 1

    # ── RIGHT: RANK DISTRIBUTION (cols 7-12) ──────────────────────────────────
    # Section header
    reqs += [
        merge(sid, rr, 7, rr+1, 13),
        write_cell(sid, rr, 7, " ◆ RANK DISTRIBUTION"),
        repeat_cell(sid, rr, 7, rr+1, 13, {
            "backgroundColor": HEADER_BG,
            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 10},
            "horizontalAlignment": "LEFT", "verticalAlignment": "MIDDLE",
        }),
        row_height(sid, rr, rr+1, 28),
    ]
    rr += 1

    # Column headers: Rank | Count | %
    reqs.append(write_row(sid, rr, 7, ["Rank", "Count", "%"]))
    reqs.append(repeat_cell(sid, rr, 7, rr+1, 10, {
        "backgroundColor": HEADER_BG,
        "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9},
        "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
    }))
    reqs.append(row_height(sid, rr, rr+1, 20))
    rr += 1

    rank_colors = {
        "Elite":    (rgb(26, 35, 126), WHITE),
        "Great":    (rgb(27, 94, 32), WHITE),
        "Good":     (rgb(0, 121, 107), WHITE),
        "Moderate": (rgb(230, 81, 0), WHITE),
        "Poor":     (rgb(183, 28, 28), WHITE),
    }
    for i, (rank, cnt) in enumerate(rank_rows):
        pct = f"{round(cnt/total*100, 1)}%" if total else "0%"
        bg, fg = rank_colors.get(rank, (WHITE if i%2==0 else GREY_LITE, DARK))
        reqs.append(write_row(sid, rr, 7, [rank, cnt, pct]))
        reqs.append(repeat_cell(sid, rr, 7, rr+1, 10, {
            "backgroundColor": bg,
            "textFormat": {"foregroundColor": fg, "bold": False, "fontSize": 9},
            "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
        }))
        reqs.append(row_height(sid, rr, rr+1, 18))
        rr += 1

    # Spacer between rank dist and priority outreach (10px)
    reqs.append(row_height(sid, rr, rr+1, 10))
    rr += 1

    # ── RIGHT: PRIORITY OUTREACH (cols 7-12) ──────────────────────────────────
    reqs += [
        merge(sid, rr, 7, rr+1, 13),
        write_cell(sid, rr, 7, " 🔥 PRIORITY OUTREACH"),
        repeat_cell(sid, rr, 7, rr+1, 13, {
            "backgroundColor": HEADER_BG,
            "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 10},
            "horizontalAlignment": "LEFT", "verticalAlignment": "MIDDLE",
        }),
        row_height(sid, rr, rr+1, 28),
    ]
    rr += 1

    # Column headers: Name | Agency | Rank | Last Booked | Months Ago
    reqs.append(write_row(sid, rr, 7, ["Name", "Agency", "Rank", "Last Booked", "Mo. Ago"]))
    reqs.append(repeat_cell(sid, rr, 7, rr+1, 13, {
        "backgroundColor": HEADER_BG,
        "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9},
        "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
    }))
    reqs.append(row_height(sid, rr, rr+1, 20))
    rr += 1

    for i, m in enumerate(hot_targets):
        lbd_str  = m["lbd"].strftime("%b %Y") if m["lbd"] else "Never"
        months   = round((TODAY - m["lbd"]).days / 30.4) if m["lbd"] else "—"
        bg       = WHITE if i % 2 == 0 else GREY_LITE
        reqs.append(write_row(sid, rr, 7, [m["name"], m["agency"], m["rank"], lbd_str, months]))
        reqs.append(repeat_cell(sid, rr, 7, rr+1, 13, {
            "backgroundColor": bg,
            "textFormat": {"foregroundColor": DARK, "bold": False, "fontSize": 9},
            "horizontalAlignment": "LEFT", "verticalAlignment": "MIDDLE",
        }))
        # Rank badge on col 9 (index 9, 3rd col in right panel = 7+2)
        reqs.append(rank_badge_cell(sid, rr, 9, m["rank"]))
        reqs.append(row_height(sid, rr, rr+1, 18))
        rr += 1

    # ── Fix row_height conflicts between left and right panels ────────────────
    # The right panel emits row_height for spacers/headers that share rows with
    # the left panel's 18px data rows. Re-apply 18px last so left wins.
    for _fix_row in range(TWO_COL_START + 2, lr):
        reqs.append(row_height(sid, _fix_row, _fix_row + 1, 18))

    # ── Gap column (col 6) coloring for two-column section ────────────────────
    gap_start = TWO_COL_START
    gap_end   = max(lr, rr)
    reqs.append(repeat_cell(sid, gap_start, 6, gap_end, 7, {
        "backgroundColor": rgb(240, 240, 240),
        "textFormat": {"foregroundColor": DARK, "fontSize": 9},
    }))

    # ── Full-width sections start after two-column area ───────────────────────
    r = max(lr, rr) + 1

    # Spacer
    reqs.append(row_height(sid, r-1, r, 14))

    # ── Section: Top 15 Most-Booked ───────────────────────────────────────────
    reqs += section_header(sid, r, 0, NUM_COLS, "  TOP 15 MOST-BOOKED MODELS")
    r += 1
    reqs.append(write_row(sid, r, 0, ["Name", "#", "Agency", "Rank", "Bookings", "Last Booked", ""]))
    reqs.append(repeat_cell(sid, r, 0, r+1, NUM_COLS, {
        "backgroundColor": HEADER_BG,
        "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9},
        "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
    }))
    reqs.append(row_height(sid, r, r+1, 20))
    r += 1

    for i, m in enumerate(top15):
        lbd_str = m["lbd"].strftime("%b %Y") if m["lbd"] else "—"
        bg = WHITE if i % 2 == 0 else GREY_LITE
        reqs.append(write_row(sid, r, 0, [m["name"], i+1, m["agency"], m["rank"], m["bookings"], lbd_str, ""]))
        reqs.append(repeat_cell(sid, r, 0, r+1, NUM_COLS, {
            "backgroundColor": bg,
            "textFormat": {"foregroundColor": DARK, "bold": False, "fontSize": 9},
            "horizontalAlignment": "LEFT", "verticalAlignment": "MIDDLE",
        }))
        # Rank badge on col 3
        reqs.append(rank_badge_cell(sid, r, 3, m["rank"]))
        # Recency coloring on col 5 (Last Booked)
        reqs.append(recency_cell(sid, r, 5, m["lbd"]))
        reqs.append(row_height(sid, r, r+1, 18))
        r += 1

    # Spacer
    reqs.append(row_height(sid, r, r+1, 14))
    r += 1

    # ── Section: Stale Re-book Targets ────────────────────────────────────────
    stale_sorted = sorted(stale, key=lambda x: x["lbd"] or date.min)
    reqs += section_header(sid, r, 0, NUM_COLS,
        f"  STALE RE-BOOK TARGETS — booked before but not in 12+ months ({len(stale_sorted)} models)")
    r += 1
    reqs.append(write_row(sid, r, 0, ["Name", "Rank", "Agency", "Bookings", "Last Booked", "Months Ago", ""]))
    reqs.append(repeat_cell(sid, r, 0, r+1, NUM_COLS, {
        "backgroundColor": HEADER_BG,
        "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9},
        "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
    }))
    reqs.append(row_height(sid, r, r+1, 20))
    r += 1

    for i, m in enumerate(stale_sorted):
        lbd_str = m["lbd"].strftime("%b %Y") if m["lbd"] else "—"
        months  = round((TODAY - m["lbd"]).days / 30.4) if m["lbd"] else 0
        bg = PURPLE_LITE if i % 2 == 0 else WHITE
        reqs.append(write_row(sid, r, 0, [m["name"], m["rank"], m["agency"],
                                          m["bookings"], lbd_str, months, ""]))
        reqs.append(repeat_cell(sid, r, 0, r+1, NUM_COLS, {
            "backgroundColor": bg,
            "textFormat": {"foregroundColor": DARK, "bold": False, "fontSize": 9},
            "horizontalAlignment": "LEFT", "verticalAlignment": "MIDDLE",
        }))
        # Rank badge on col 1 (narrow col fits badge nicely)
        reqs.append(rank_badge_cell(sid, r, 1, m["rank"]))
        # Recency coloring on col 4 (Last Booked)
        reqs.append(recency_cell(sid, r, 4, m["lbd"]))
        reqs.append(row_height(sid, r, r+1, 18))
        r += 1

    # Spacer
    reqs.append(row_height(sid, r, r+1, 14))
    r += 1

    # ── Section: Never Booked ─────────────────────────────────────────────────
    reqs += section_header(sid, r, 0, NUM_COLS,
        f"  NEVER BOOKED — {len(unbooked)} models with no bookings recorded")
    r += 1
    reqs.append(write_row(sid, r, 0, ["Name", "Rank", "Agency", "Location", ""]))
    reqs.append(repeat_cell(sid, r, 0, r+1, NUM_COLS, {
        "backgroundColor": HEADER_BG,
        "textFormat": {"foregroundColor": WHITE, "bold": True, "fontSize": 9},
        "horizontalAlignment": "CENTER", "verticalAlignment": "MIDDLE",
    }))
    reqs.append(row_height(sid, r, r+1, 20))
    r += 1

    for i, m in enumerate(sorted(unbooked, key=lambda x: x["agency"])):
        bg = RED_LITE if i % 2 == 0 else WHITE
        reqs.append(write_row(sid, r, 0, [m["name"], m["rank"], m["agency"], m["location"], ""]))
        reqs.append(repeat_cell(sid, r, 0, r+1, NUM_COLS, {
            "backgroundColor": bg,
            "textFormat": {"foregroundColor": DARK, "bold": False, "fontSize": 9},
            "horizontalAlignment": "LEFT", "verticalAlignment": "MIDDLE",
        }))
        # Rank badge on col 1
        reqs.append(rank_badge_cell(sid, r, 1, m["rank"]))
        reqs.append(row_height(sid, r, r+1, 18))
        r += 1

    # ── Hide gridlines + freeze first 8 rows ─────────────────────────────────
    reqs += [
        {"updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {"hideGridlines": True}},
            "fields": "gridProperties.hideGridlines",
        }},
        {"updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 8}},
            "fields": "gridProperties.frozenRowCount",
        }},
    ]

    # ── Send ──────────────────────────────────────────────────────────────────
    print(f"Sending {len(reqs)} requests…")
    send(service, reqs)
    print(f"\n✅ Dashboard created with {r} rows of data.")


if __name__ == "__main__":
    main()
