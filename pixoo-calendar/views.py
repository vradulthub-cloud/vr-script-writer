"""View renderers for the 64x64 Pixoo display.
Uses pixel-perfect bitmap font — no antialiasing."""

import os
import random
from datetime import datetime, timedelta
from PIL import Image, ImageDraw
from calendar_data import Event
from pixelfont import draw_text, draw_big, text_width, big_text_width, CHAR_H, BIG_H
from icons import draw_icon
from weather import fetch_weather, load_cached_weather
from scenes import generate_lofi_frames

SIZE = 64

# Color palette
BG = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (80, 80, 80)
DIM = (40, 40, 40)
CYAN = (0, 200, 220)
ORANGE = (255, 140, 0)
GREEN = (0, 200, 80)
RED = (220, 50, 50)
PURPLE = (160, 80, 255)
BLUE = (60, 120, 255)
YELLOW = (255, 220, 0)
PINK = (255, 100, 180)

# Calendar name -> color
CAL_COLORS = {}
COLOR_POOL = [CYAN, ORANGE, GREEN, PURPLE, BLUE, YELLOW, RED, PINK]


def _get_cal_color(cal_name: str) -> tuple:
    if cal_name not in CAL_COLORS:
        CAL_COLORS[cal_name] = COLOR_POOL[len(CAL_COLORS) % len(COLOR_POOL)]
    return CAL_COLORS[cal_name]


def _time_str(dt: datetime) -> str:
    h = dt.hour % 12 or 12
    return f"{h}:{dt.minute:02d}"


def _ampm(dt: datetime) -> str:
    return "a" if dt.hour < 12 else "p"


def _header(img: Image.Image, draw: ImageDraw.Draw, text: str, color: tuple):
    """Draw header bar."""
    draw.rectangle([0, 0, 63, 8], fill=(15, 15, 30))
    draw_text(img, 2, 1, text, color)
    # Time in top right
    now = datetime.now()
    ts = f"{now.hour % 12 or 12}:{now.minute:02d}"
    draw_text(img, 64 - text_width(ts) - 1, 1, ts, GRAY)


def _progress_bar(draw: ImageDraw.Draw):
    """Thin day-progress bar at the very bottom."""
    now = datetime.now()
    frac = (now.hour * 60 + now.minute) / (24 * 60)
    w = max(1, int(63 * frac))
    draw.rectangle([0, 63, w, 63], fill=(30, 30, 50))


def render_agenda(events: list[Event]) -> Image.Image:
    """View 1: Today's agenda list."""
    img = Image.new("RGB", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)

    _header(img, draw, "TODAY", CYAN)
    _progress_bar(draw)

    today = [e for e in events if e.start.date() == datetime.now().date()]

    if not today:
        draw_text(img, 10, 28, "No events", GRAY)
        draw_text(img, 14, 38, "today", GRAY)
        return img

    y = 11
    for evt in today[:7]:
        if y > 56:
            break
        color = _get_cal_color(evt.calendar)
        # Color dot
        draw.rectangle([1, y + 1, 2, y + 4], fill=color)

        if evt.all_day:
            draw_text(img, 4, y, "ALL", DIM)
        else:
            draw_text(img, 4, y, _time_str(evt.start), GRAY)

        # Title
        draw_text(img, 30, y, evt.title[:7], WHITE)
        y += CHAR_H + 1

    return img


def render_week(events: list[Event]) -> Image.Image:
    """View 2: 7-day week grid with busy blocks."""
    img = Image.new("RGB", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)

    _header(img, draw, "WEEK", PURPLE)

    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    days = [monday + timedelta(days=i) for i in range(7)]
    labels = ["M", "T", "W", "T", "F", "S", "S"]

    col_w = 9
    top = 10
    grid_top = 18  # Below day labels

    for i, (day, label) in enumerate(zip(days, labels)):
        x = i * col_w
        # Day label
        is_today = day == today
        draw_text(img, x + 2, top, label, CYAN if is_today else GRAY)

        # Today underline
        if is_today:
            draw.rectangle([x + 1, top + 7, x + col_w - 2, top + 7], fill=CYAN)

        # Event blocks (7am-10pm mapped to grid)
        day_events = [e for e in events if e.start.date() == day and not e.all_day]
        for evt in day_events:
            h_start = max(evt.start.hour + evt.start.minute / 60, 7)
            h_end = min(evt.end.hour + evt.end.minute / 60, 22)
            if h_end <= h_start:
                continue
            py_s = grid_top + int((h_start - 7) / 15 * 44)
            py_e = grid_top + int((h_end - 7) / 15 * 44)
            color = _get_cal_color(evt.calendar)
            draw.rectangle([x + 1, py_s, x + col_w - 2, max(py_e, py_s + 2)], fill=color)

        # All-day: thin bar at grid top
        if any(e.start.date() == day and e.all_day for e in events):
            draw.rectangle([x + 1, grid_top, x + col_w - 2, grid_top + 1], fill=ORANGE)

    return img


def render_countdown(events: list[Event]) -> Image.Image:
    """View 3: Big countdown to next event."""
    img = Image.new("RGB", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)

    _header(img, draw, "NEXT", ORANGE)
    _progress_bar(draw)

    now = datetime.now()
    upcoming = [e for e in events if e.start > now and not e.all_day]

    if not upcoming:
        draw_text(img, 8, 24, "All clear!", GREEN)
        # Little check mark
        draw.line([(28, 36), (32, 40), (40, 32)], fill=GREEN, width=1)
        return img

    nxt = upcoming[0]
    delta = nxt.start - now
    total_min = int(delta.total_seconds() / 60)
    hours = total_min // 60
    mins = total_min % 60

    # Color based on urgency
    if total_min <= 15:
        color = RED
    elif total_min <= 60:
        color = ORANGE
    else:
        color = CYAN

    # Big countdown centered
    if hours > 0:
        cd = f"{hours}:{mins:02d}"
    else:
        cd = f"{mins}m"

    tw = big_text_width(cd)
    draw_big(img, (64 - tw) // 2, 14, cd, color)

    # Divider line
    draw.rectangle([8, 28, 55, 28], fill=DIM)

    # Event title (up to 2 lines)
    title = nxt.title
    draw_text(img, 2, 32, title[:12], WHITE)
    if len(title) > 12:
        draw_text(img, 2, 32 + CHAR_H, title[12:24], WHITE)

    # Event time at bottom
    t = _time_str(nxt.start) + _ampm(nxt.start)
    draw_text(img, 2, 55, t, GRAY)

    return img


def render_now_upcoming(events: list[Event]) -> Image.Image:
    """View 4: Current event + upcoming list."""
    img = Image.new("RGB", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)

    _header(img, draw, "NOW", GREEN)
    _progress_bar(draw)

    now = datetime.now()
    today_events = [e for e in events if e.start.date() == now.date() and not e.all_day]

    current = None
    upcoming = []
    for evt in today_events:
        if evt.start <= now < evt.end:
            current = evt
        elif evt.start > now:
            upcoming.append(evt)

    y = 11
    if current:
        color = _get_cal_color(current.calendar)
        # Highlighted block
        draw.rectangle([0, y, 63, y + 16], fill=(15, 25, 15))
        draw.rectangle([0, y, 1, y + 16], fill=color)
        draw_text(img, 3, y + 1, "NOW", GREEN)
        draw_text(img, 3, y + 9, current.title[:12], WHITE)
        y += 19
    else:
        draw_text(img, 3, y, "Free now", GREEN)
        y += CHAR_H + 3

    # Divider
    draw.rectangle([3, y, 60, y], fill=DIM)
    y += 3

    # Upcoming
    for evt in upcoming[:4]:
        if y > 56:
            break
        color = _get_cal_color(evt.calendar)
        draw.rectangle([1, y + 1, 2, y + 4], fill=color)
        draw_text(img, 4, y, _time_str(evt.start), GRAY)
        draw_text(img, 30, y, evt.title[:7], WHITE)
        y += CHAR_H + 1

    if not current and not upcoming:
        draw_text(img, 10, 30, "No events", GRAY)

    return img


def render_clock_weather(events: list[Event]) -> list[Image.Image]:
    """View 5: Animated lo-fi cozy scene with clock + weather overlaid.
    Returns a list of frames for animation."""
    frames = generate_lofi_frames(num_frames=6)

    now = datetime.now()
    h = now.hour % 12 or 12
    time_str = f"{h}:{now.minute:02d}"
    tw = big_text_width(time_str)
    ampm = "a" if now.hour < 12 else "p"
    # Append am/pm right after time for compact display
    full_time = f"{h}:{now.minute:02d}"

    WARM = (230, 210, 170)
    WARM_DIM = (150, 130, 100)

    weather = load_cached_weather()
    if not weather:
        weather = fetch_weather()

    # Overlay clock + weather on each frame
    for img in frames:
        draw = ImageDraw.Draw(img)

        # Dark backdrop behind clock for readability
        draw.rectangle([19, 7, 58, 26], fill=(10, 15, 40))

        # Clock centered in window
        cx = 20 + (38 - tw) // 2
        draw_big(img, cx, 9, full_time, WARM)
        # am/pm right after
        draw_text(img, cx + tw + 1, 13, ampm, WARM_DIM)

        # Date below clock
        days = ["Mon", "Tu", "Wed", "Th", "Fri", "Sat", "Sun"]
        date_str = f"{days[now.weekday()]} {now.day}"
        dtw = text_width(date_str)
        draw_text(img, 20 + (38 - dtw) // 2, 20, date_str, CYAN)

        # Weather on desk — centered, abbreviated
        if weather:
            temp_str = f"{int(weather.temp)}F"
            desc = weather.description[:8]
            # Center the combined string
            combined = f"{temp_str} {desc}"
            cw = text_width(combined)
            draw_text(img, (64 - cw) // 2, 57, combined, ORANGE)

    return frames


PHOTOS_DIR = os.path.join(os.path.dirname(__file__), "photos")


def render_photo(events: list[Event]) -> Image.Image:
    """View 6: Random photo from local gallery, pixel-art scaled."""
    img = Image.new("RGB", (SIZE, SIZE), BG)

    if not os.path.isdir(PHOTOS_DIR):
        os.makedirs(PHOTOS_DIR, exist_ok=True)

    photos = [
        f for f in os.listdir(PHOTOS_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp"))
    ]

    if not photos:
        draw = ImageDraw.Draw(img)
        draw_text(img, 6, 24, "Add photos", GRAY)
        draw_text(img, 14, 34, "to the", GRAY)
        draw_text(img, 4, 44, "photos/ dir", GRAY)
        return img

    # Pick a random photo
    photo_path = os.path.join(PHOTOS_DIR, random.choice(photos))
    try:
        photo = Image.open(photo_path).convert("RGB")
        # Crop to square from center
        w, h = photo.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        photo = photo.crop((left, top, left + side, top + side))
        # Scale to 64x64 with LANCZOS for best quality
        photo = photo.resize((SIZE, SIZE), Image.LANCZOS)
        return photo
    except Exception as e:
        draw = ImageDraw.Draw(img)
        draw_text(img, 8, 28, "Photo err", RED)
        return img


VIEWS = [
    ("agenda", render_agenda),
    ("week", render_week),
    ("countdown", render_countdown),
    ("now_upcoming", render_now_upcoming),
    ("clock_weather", render_clock_weather),
    ("photo", render_photo),
]
