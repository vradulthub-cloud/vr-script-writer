#!/usr/bin/env python3
"""Pixoo64 Smart Hub Calendar — main entry point."""

import argparse
import json
import sys
from pathlib import Path

from calendar_data import get_today_events, get_week_events
from device import get_device_ip, push_image, discover_device, save_config, load_config
from views import VIEWS

STATE_PATH = Path(__file__).parent / "state.json"


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"view_index": 0}


def save_state(state: dict):
    STATE_PATH.write_text(json.dumps(state))


def main():
    parser = argparse.ArgumentParser(description="Pixoo64 Smart Hub Calendar")
    parser.add_argument("--ip", help="Device IP address (skips discovery)")
    parser.add_argument("--discover", action="store_true", help="Discover device and exit")
    parser.add_argument("--view", choices=[name for name, _ in VIEWS], help="Force a specific view")
    parser.add_argument("--preview", action="store_true", help="Save preview image instead of pushing to device")
    args = parser.parse_args()

    # Discovery mode
    if args.discover:
        ip = discover_device()
        if ip:
            print(f"Found Pixoo64 at {ip}")
            config = load_config()
            config["device_ip"] = ip
            save_config(config)
        else:
            print("No Pixoo64 found on LAN")
            sys.exit(1)
        return

    # Manual IP override
    if args.ip:
        config = load_config()
        config["device_ip"] = args.ip
        save_config(config)

    # Determine which view to render
    state = load_state()
    if args.view:
        view_idx = next(i for i, (name, _) in enumerate(VIEWS) if name == args.view)
    else:
        view_idx = state["view_index"] % len(VIEWS)

    view_name, render_fn = VIEWS[view_idx]
    print(f"Rendering view: {view_name}")

    # Fetch calendar data
    if view_name == "week":
        events = get_week_events()
    else:
        events = get_today_events()

    # Render — may return a single Image or a list of frames
    result = render_fn(events)
    is_animation = isinstance(result, list)

    if args.preview:
        preview_path = Path(__file__).parent / f"preview_{view_name}.png"
        preview_img = result[0] if is_animation else result
        scaled = preview_img.resize((256, 256), resample=0)
        scaled.save(preview_path)
        if is_animation:
            # Also save a GIF preview
            gif_path = Path(__file__).parent / f"preview_{view_name}.gif"
            frames_scaled = [f.resize((256, 256), resample=0) for f in result]
            frames_scaled[0].save(gif_path, save_all=True,
                                  append_images=frames_scaled[1:],
                                  duration=500, loop=0)
            print(f"Animation preview saved: {gif_path} ({len(result)} frames)")
        print(f"Preview saved: {preview_path}")
    else:
        # Push to device
        ip = get_device_ip()
        push_image(ip, result)
        kind = f"animation ({len(result)} frames)" if is_animation else "image"
        print(f"Pushed {kind} to Pixoo64")

    # Advance to next view
    state["view_index"] = (view_idx + 1) % len(VIEWS)
    save_state(state)


if __name__ == "__main__":
    main()
