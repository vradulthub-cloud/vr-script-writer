"""Calendar data: fetch via AppleScript (slow) + cache to JSON (fast reads)."""

import json
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path

CACHE_PATH = Path(__file__).parent / "calendar_cache.json"

# Which calendars to query (add/remove as needed)
CALENDARS = ["Work", "Home", "Calendar", "Char Night Schedule", "Michael Ninn"]

# AppleScript date format
DATE_FORMATS = [
    "%A, %B %d, %Y at %I:%M:%S %p",
    "%A, %B %d, %Y at %H:%M:%S",
]


@dataclass
class Event:
    calendar: str
    title: str
    start: datetime
    end: datetime
    all_day: bool = False

    def to_dict(self) -> dict:
        return {
            "calendar": self.calendar,
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "all_day": self.all_day,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(
            calendar=d["calendar"],
            title=d["title"],
            start=datetime.fromisoformat(d["start"]),
            end=datetime.fromisoformat(d["end"]),
            all_day=d.get("all_day", False),
        )


def _parse_date(s: str) -> datetime:
    s = s.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s!r}")


def _is_all_day(start: datetime, end: datetime) -> bool:
    return start.hour == 0 and start.minute == 0 and (end - start) >= timedelta(hours=23)


def fetch_and_cache(days: int = 7):
    """Fetch events from macOS Calendar via AppleScript and write to cache.

    This is the SLOW operation (~60s). Run it infrequently.
    """
    # Build calendar name list for AppleScript
    cal_list = ", ".join(f'"{c}"' for c in CALENDARS)

    script = f'''
set today to current date
set time of today to 0
set endDate to today + ({days} * days)
set output to ""
tell application "Calendar"
    set calNames to {{{cal_list}}}
    repeat with cName in calNames
        try
            set cal to calendar cName
            set calEvents to (every event of cal whose start date >= today and start date < endDate)
            repeat with evt in calEvents
                set output to output & cName & "|" & (summary of evt) & "|" & ((start date of evt) as string) & "|" & ((end date of evt) as string) & linefeed
            end repeat
        end try
    end repeat
end tell
return output
'''
    print(f"Fetching events for {days} days from {len(CALENDARS)} calendars...")
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        print(f"AppleScript error: {result.stderr}", file=sys.stderr)
        return

    events = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 4:
            continue
        cal, title, start_str, end_str = parts[0], parts[1], parts[2], parts[3]
        try:
            start = _parse_date(start_str)
            end = _parse_date(end_str)
            events.append(Event(
                calendar=cal.strip(),
                title=title.strip(),
                start=start,
                end=end,
                all_day=_is_all_day(start, end),
            ))
        except ValueError as e:
            print(f"Skipping event: {e}", file=sys.stderr)

    events.sort(key=lambda e: (e.all_day, e.start))

    cache = {
        "fetched_at": datetime.now().isoformat(),
        "events": [e.to_dict() for e in events],
    }
    CACHE_PATH.write_text(json.dumps(cache, indent=2))
    print(f"Cached {len(events)} events to {CACHE_PATH}")


def load_events() -> list[Event]:
    """Load events from cache. Fast — just reads JSON."""
    if not CACHE_PATH.exists():
        print("No cache found. Run: python fetch_calendar.py")
        return []

    data = json.loads(CACHE_PATH.read_text())
    return [Event.from_dict(d) for d in data["events"]]


def get_today_events() -> list[Event]:
    today = datetime.now().date()
    return [e for e in load_events() if e.start.date() == today]


def get_week_events() -> list[Event]:
    today = datetime.now().date()
    week_end = today + timedelta(days=7)
    return [e for e in load_events() if today <= e.start.date() < week_end]


if __name__ == "__main__":
    # Run directly to refresh cache
    fetch_and_cache()

    # Also refresh weather
    from weather import fetch_weather
    w = fetch_weather()
    if w:
        print(f"Weather: {w.temp}F, {w.description}")
