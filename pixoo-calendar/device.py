"""Pixoo64 device discovery and communication via raw HTTP API."""

import base64
import io
import json
from pathlib import Path

import requests
from PIL import Image

CONFIG_PATH = Path(__file__).parent / "config.json"
DIVOOM_DISCOVERY_URL = "https://app.divoom-gz.com/Device/ReturnSameLANDevice"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}


def save_config(config: dict):
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


def discover_device() -> str | None:
    """Find Pixoo64 on LAN via Divoom's cloud discovery API."""
    try:
        resp = requests.post(DIVOOM_DISCOVERY_URL, json={}, timeout=5)
        data = resp.json()
        devices = data.get("DeviceList", [])
        for dev in devices:
            if "64" in dev.get("DeviceName", ""):
                return dev.get("DevicePrivateIP")
        if devices:
            return devices[0].get("DevicePrivateIP")
    except Exception as e:
        print(f"Discovery failed: {e}")
    return None


def get_device_ip(ip_override: str | None = None) -> str:
    """Get the device IP. Discovers if needed."""
    config = load_config()
    ip = ip_override or config.get("device_ip")

    if not ip:
        print("Discovering Pixoo64 on LAN...")
        ip = discover_device()
        if not ip:
            raise RuntimeError(
                "Could not find Pixoo64. Run with --ip <address> to set manually."
            )
        print(f"Found device at {ip}")
        config["device_ip"] = ip
        save_config(config)

    return ip


def _image_to_rgb_list(image: Image.Image) -> list[int]:
    """Convert a 64x64 PIL Image to a flat list of R,G,B values."""
    img = image.convert("RGB").resize((64, 64))
    pixels = list(img.getdata())
    flat = []
    for r, g, b in pixels:
        flat.extend([r, g, b])
    return flat


def push_image(ip: str, image):
    """Push image(s) to the Pixoo64. Accepts a single Image or a list of frames."""
    if isinstance(image, list):
        return push_animation(ip, image)
    return _push_single(ip, image)


def _push_single(ip: str, image: Image.Image):
    """Push a single 64x64 frame."""
    url = f"http://{ip}/post"

    try:
        requests.post(url, json={"Command": "Draw/ResetHttpGifId"}, timeout=10)
    except requests.exceptions.Timeout:
        pass

    rgb_data = _image_to_rgb_list(image)
    encoded = base64.b64encode(bytes(rgb_data)).decode("ascii")

    payload = {
        "Command": "Draw/SendHttpGif",
        "PicNum": 1,
        "PicWidth": 64,
        "PicOffset": 0,
        "PicID": 0,
        "PicSpeed": 1000,
        "PicData": encoded,
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        return resp.json()
    except requests.exceptions.Timeout:
        return {"status": "sent (response timed out)"}


def push_animation(ip: str, frames: list, speed: int = 500):
    """Push a multi-frame animation to the Pixoo64."""
    url = f"http://{ip}/post"

    try:
        requests.post(url, json={"Command": "Draw/ResetHttpGifId"}, timeout=10)
    except requests.exceptions.Timeout:
        pass

    num_frames = len(frames)
    for i, frame in enumerate(frames):
        rgb_data = _image_to_rgb_list(frame)
        encoded = base64.b64encode(bytes(rgb_data)).decode("ascii")

        payload = {
            "Command": "Draw/SendHttpGif",
            "PicNum": num_frames,
            "PicWidth": 64,
            "PicOffset": i,
            "PicID": 0,
            "PicSpeed": speed,
            "PicData": encoded,
        }

        try:
            requests.post(url, json=payload, timeout=15)
        except requests.exceptions.Timeout:
            pass

    return {"status": f"sent {num_frames} frames"}


def set_brightness(ip: str, brightness: int):
    """Set display brightness (0-100)."""
    url = f"http://{ip}/post"
    requests.post(url, json={
        "Command": "Channel/SetBrightness",
        "Brightness": max(0, min(100, brightness)),
    }, timeout=5)
