"""Pixel art scene backgrounds with animation frames.
Designed for LED displays — bold colors, high contrast, simple shapes."""

import random
from PIL import Image, ImageDraw

# Lo-fi cozy palette — bright and bold for LEDs
C = {
    "bg": (10, 8, 18),
    "wall": (28, 20, 32),
    "frame": (90, 60, 42),
    "frame_hi": (120, 80, 55),
    "glass_top": (18, 28, 65),
    "glass_bot": (38, 32, 75),
    "cloud": (45, 50, 85),
    "rain": (80, 130, 220),
    "rain2": (60, 100, 180),
    "sill": (110, 75, 48),
    "desk": (55, 35, 25),
    "desk_hi": (85, 58, 38),
    "pot": (180, 90, 45),
    "leaf": (55, 190, 75),
    "leaf_dk": (35, 130, 50),
    "mug": (210, 190, 150),
    "steam1": (100, 100, 130),
    "steam2": (70, 70, 100),
    "cat": (75, 65, 58),
    "cat_eye": (190, 210, 90),
    "shade": (230, 190, 80),
    "shade_dim": (200, 160, 60),
    "pole": (100, 80, 60),
}

# Window geometry
WX, WY, WW, WH = 16, 1, 44, 32


def _draw_base(img: Image.Image):
    """Draw the static parts of the scene."""
    draw = ImageDraw.Draw(img)

    # Background with subtle texture
    draw.rectangle([0, 0, 63, 63], fill=C["bg"])
    for y in range(64):
        for x in range(64):
            if (x + y * 3) % 11 == 0:
                img.putpixel((x, y), C["wall"])

    # Window frame
    draw.rectangle([WX - 2, WY - 1, WX + WW + 1, WY + WH + 1], fill=C["frame"])
    draw.rectangle([WX - 2, WY - 1, WX + WW + 1, WY], fill=C["frame_hi"])

    # Glass gradient
    mid_x = WX + WW // 2
    for y in range(WY + 1, WY + WH):
        frac = (y - WY) / WH
        r = int(C["glass_top"][0] + (C["glass_bot"][0] - C["glass_top"][0]) * frac)
        g = int(C["glass_top"][1] + (C["glass_bot"][1] - C["glass_top"][1]) * frac)
        b = int(C["glass_top"][2] + (C["glass_bot"][2] - C["glass_top"][2]) * frac)
        draw.line([(WX, y), (mid_x - 2, y)], fill=(r, g, b))
        draw.line([(mid_x + 1, y), (WX + WW - 1, y)], fill=(r, g, b))

    # Divider
    draw.rectangle([mid_x - 1, WY + 1, mid_x, WY + WH - 1], fill=C["frame"])

    # Clouds
    for cx, cy, cw in [(20, 6, 8), (38, 4, 10), (50, 9, 6)]:
        draw.rectangle([cx, cy, cx + cw, cy + 2], fill=C["cloud"])

    # Sill
    draw.rectangle([WX - 3, WY + WH + 1, WX + WW + 2, WY + WH + 3], fill=C["sill"])

    # Plant on sill
    px = WX + WW - 6
    py = WY + WH - 1
    draw.rectangle([px, py + 2, px + 4, py + 4], fill=C["pot"])
    draw.rectangle([px - 1, py + 2, px + 5, py + 2], fill=C["pot"])
    for lx, ly, col in [
        (px + 2, py, C["leaf"]), (px + 1, py + 1, C["leaf"]),
        (px + 3, py + 1, C["leaf"]), (px, py - 1, C["leaf"]),
        (px + 4, py - 1, C["leaf"]), (px + 1, py - 1, C["leaf_dk"]),
        (px + 3, py - 1, C["leaf_dk"]), (px + 2, py - 2, C["leaf"]),
    ]:
        if 0 <= lx < 64 and 0 <= ly < 64:
            img.putpixel((lx, ly), col)

    # Mug on sill
    mx = WX + 2
    my = WY + WH - 2
    draw.rectangle([mx, my + 1, mx + 4, my + 4], fill=C["mug"])
    img.putpixel((mx + 5, my + 2), C["mug"])
    img.putpixel((mx + 5, my + 3), C["mug"])

    # Desk
    draw.rectangle([0, 55, 63, 63], fill=C["desk"])
    draw.rectangle([0, 55, 63, 55], fill=C["desk_hi"])

    # Cat
    cx, cy = 2, 48
    draw.rectangle([cx, cy + 2, cx + 6, cy + 6], fill=C["cat"])
    draw.rectangle([cx + 4, cy, cx + 8, cy + 3], fill=C["cat"])
    img.putpixel((cx + 4, cy - 1), C["cat"])
    img.putpixel((cx + 8, cy - 1), C["cat"])
    img.putpixel((cx + 5, cy + 1), C["cat_eye"])
    img.putpixel((cx + 7, cy + 1), C["cat_eye"])
    img.putpixel((cx - 1, cy + 3), C["cat"])
    img.putpixel((cx - 2, cy + 2), C["cat"])

    # Lamp
    lx = 56
    draw.rectangle([lx + 2, 46, lx + 3, 54], fill=C["pole"])
    draw.rectangle([lx, 54, lx + 5, 55], fill=C["pole"])


def _draw_dynamic(img: Image.Image, frame: int):
    """Draw animated elements for a specific frame."""
    draw = ImageDraw.Draw(img)

    # === RAIN — shifts down each frame ===
    rng = random.Random(123)  # Deterministic base positions
    for i in range(20):
        rx = rng.randint(WX + 1, WX + WW - 2)
        base_ry = rng.randint(WY + 2, WY + WH - 4)
        # Animate: shift down by frame offset, wrap within window
        ry = WY + 2 + (base_ry - WY - 2 + frame * 3) % (WH - 5)
        col = C["rain"] if i % 2 == 0 else C["rain2"]
        if WY + 1 < ry < WY + WH - 1:
            img.putpixel((rx, ry), col)
            img.putpixel((rx, ry + 1), col)

    # === STEAM from mug — drifts up and sideways ===
    mx = WX + 3
    my = WY + WH - 3
    steam_positions = [
        [(mx, my), (mx + 1, my - 1), (mx - 1, my - 2)],
        [(mx + 1, my), (mx, my - 1), (mx + 1, my - 2)],
        [(mx, my), (mx - 1, my - 1), (mx, my - 2)],
        [(mx - 1, my), (mx, my - 1), (mx - 1, my - 2)],
        [(mx + 1, my), (mx + 1, my - 1), (mx, my - 2)],
        [(mx, my), (mx + 1, my - 1), (mx + 1, my - 2)],
    ]
    steam = steam_positions[frame % len(steam_positions)]
    for i, (sx, sy) in enumerate(steam):
        col = C["steam1"] if i == 0 else C["steam2"]
        if 0 <= sx < 64 and 0 <= sy < 64:
            img.putpixel((sx, sy), col)

    # === LAMP — flickers between bright/dim ===
    lx = 56
    shade_col = C["shade"] if frame % 3 != 2 else C["shade_dim"]
    draw.rectangle([lx - 1, 43, lx + 6, 46], fill=shade_col)

    # Lamp glow pool — varies with flicker
    glow_intensity = 30 if frame % 3 != 2 else 18
    for gy in range(47, 55):
        for gx in range(lx - 3, lx + 9):
            if 0 <= gx < 64:
                r, g, b = img.getpixel((gx, gy))
                img.putpixel((gx, gy), (
                    min(255, r + glow_intensity),
                    min(255, g + int(glow_intensity * 0.7)),
                    min(255, b + int(glow_intensity * 0.15)),
                ))

    # === CAT TAIL — sways ===
    cx, cy = 2, 48
    # Clear old tail area
    img.putpixel((cx - 1, cy + 4), C["bg"])
    img.putpixel((cx - 2, cy + 3), C["bg"])
    img.putpixel((cx - 3, cy + 2), C["bg"])
    img.putpixel((cx - 1, cy + 3), C["bg"])
    img.putpixel((cx - 2, cy + 2), C["bg"])
    img.putpixel((cx - 3, cy + 1), C["bg"])
    # Draw tail in new position
    tail_positions = [
        [(cx - 1, cy + 3), (cx - 2, cy + 2)],
        [(cx - 1, cy + 3), (cx - 2, cy + 2), (cx - 3, cy + 1)],
        [(cx - 1, cy + 3), (cx - 2, cy + 2)],
        [(cx - 1, cy + 4), (cx - 2, cy + 3), (cx - 3, cy + 2)],
    ]
    for tx, ty in tail_positions[frame % len(tail_positions)]:
        if 0 <= tx < 64 and 0 <= ty < 64:
            img.putpixel((tx, ty), C["cat"])


def generate_lofi_frames(num_frames: int = 6) -> list[Image.Image]:
    """Generate animation frames for the lo-fi scene."""
    # Draw base once, copy for each frame
    base = Image.new("RGB", (64, 64), C["bg"])
    _draw_base(base)

    frames = []
    for f in range(num_frames):
        frame = base.copy()
        _draw_dynamic(frame, f)
        frames.append(frame)

    return frames
