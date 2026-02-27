"""Weather API integration for auto-filling ambient conditions."""

import httpx
from datetime import datetime

from app.core.config import settings


async def fetch_weather(
    lat: float,
    lon: float,
    dt: datetime | None = None,
) -> dict | None:
    """Fetch weather data for a GPS location and time.

    Uses OpenWeatherMap API. Falls back gracefully if no API key is set.
    For historical data, uses the onecall/timemachine endpoint.
    For current data, uses the weather endpoint.
    """
    if not settings.openweather_api_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if dt and (datetime.utcnow() - dt).total_seconds() > 3600:
                timestamp = int(dt.timestamp())
                url = (
                    f"https://api.openweathermap.org/data/3.0/onecall/timemachine"
                    f"?lat={lat}&lon={lon}&dt={timestamp}"
                    f"&appid={settings.openweather_api_key}&units=imperial"
                )
            else:
                url = (
                    f"https://api.openweathermap.org/data/2.5/weather"
                    f"?lat={lat}&lon={lon}"
                    f"&appid={settings.openweather_api_key}&units=imperial"
                )

            resp = await client.get(url)
            if resp.status_code != 200:
                return None

            data = resp.json()

            if "data" in data:
                entry = data["data"][0] if isinstance(data["data"], list) else data["data"]
                return {
                    "ambient_temp_f": entry.get("temp"),
                    "track_temp_f": None,
                    "humidity_pct": entry.get("humidity"),
                    "wind_speed_mph": entry.get("wind_speed"),
                    "wind_direction": _degrees_to_cardinal(entry.get("wind_deg", 0)),
                    "conditions": entry.get("weather", [{}])[0].get("description", ""),
                    "source": "openweathermap",
                }
            else:
                main = data.get("main", {})
                wind = data.get("wind", {})
                weather = data.get("weather", [{}])
                return {
                    "ambient_temp_f": main.get("temp"),
                    "track_temp_f": None,
                    "humidity_pct": main.get("humidity"),
                    "wind_speed_mph": wind.get("speed"),
                    "wind_direction": _degrees_to_cardinal(wind.get("deg", 0)),
                    "conditions": weather[0].get("description", "") if weather else "",
                    "source": "openweathermap",
                }

    except Exception:
        return None


def _degrees_to_cardinal(degrees: float) -> str:
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = round(degrees / 22.5) % 16
    return dirs[idx]
