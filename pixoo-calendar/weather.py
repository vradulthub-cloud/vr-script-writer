"""Weather data via Open-Meteo (free, no API key needed)."""

import json
import requests
from dataclasses import dataclass
from pathlib import Path

CACHE_PATH = Path(__file__).parent / "weather_cache.json"

# WMO Weather codes -> description + icon name
WMO_CODES = {
    0: ("Clear", "sun"),
    1: ("Mostly Clear", "sun"),
    2: ("Partly Cloudy", "cloud_sun"),
    3: ("Overcast", "cloud"),
    45: ("Foggy", "fog"),
    48: ("Fog", "fog"),
    51: ("Light Drizzle", "rain_light"),
    53: ("Drizzle", "rain_light"),
    55: ("Heavy Drizzle", "rain"),
    61: ("Light Rain", "rain_light"),
    63: ("Rain", "rain"),
    65: ("Heavy Rain", "rain"),
    71: ("Light Snow", "snow"),
    73: ("Snow", "snow"),
    75: ("Heavy Snow", "snow"),
    80: ("Showers", "rain"),
    81: ("Heavy Showers", "rain"),
    82: ("Violent Showers", "rain"),
    95: ("Thunderstorm", "storm"),
    96: ("Thunderstorm + Hail", "storm"),
    99: ("Thunderstorm + Hail", "storm"),
}


@dataclass
class Weather:
    temp: float
    high: float
    low: float
    code: int
    description: str
    icon: str


def fetch_weather(lat: float = 34.05, lon: float = -118.24) -> Weather | None:
    """Fetch current weather. Returns None on failure."""
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min",
            "temperature_unit": "fahrenheit",
            "timezone": "auto",
            "forecast_days": 1,
        }, timeout=10)
        data = r.json()
        code = data["current"]["weather_code"]
        desc, icon = WMO_CODES.get(code, ("Unknown", "cloud"))
        w = Weather(
            temp=round(data["current"]["temperature_2m"]),
            high=round(data["daily"]["temperature_2m_max"][0]),
            low=round(data["daily"]["temperature_2m_min"][0]),
            code=code,
            description=desc,
            icon=icon,
        )
        # Cache it
        CACHE_PATH.write_text(json.dumps({
            "temp": w.temp, "high": w.high, "low": w.low,
            "code": w.code, "description": w.description, "icon": w.icon,
        }))
        return w
    except Exception as e:
        print(f"Weather fetch failed: {e}")
        return load_cached_weather()


def load_cached_weather() -> Weather | None:
    if not CACHE_PATH.exists():
        return None
    d = json.loads(CACHE_PATH.read_text())
    return Weather(**d)
