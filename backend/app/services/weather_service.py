"""Fetch historical weather data from Open-Meteo for a given track session.

Uses the free Open-Meteo API (no key required):
  - Historical archive for dates > 5 days old
  - Forecast API for recent/current dates (includes past 5 days)
"""

from __future__ import annotations

import logging
from datetime import datetime, date, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "precipitation",
    "surface_pressure",
    "cloud_cover",
]


def _c_to_f(c: float) -> float:
    return round(c * 9 / 5 + 32, 1)


def _kmh_to_mph(kmh: float) -> float:
    return round(kmh * 0.621371, 1)


def _wind_direction_label(deg: float) -> str:
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = round(deg / 22.5) % 16
    return dirs[idx]


def _assess_grip_conditions(
    air_temp_c: float,
    humidity: float,
    precipitation: float,
) -> dict:
    """Produce a qualitative grip assessment for coaching context."""
    notes: list[str] = []
    rating = "good"

    if precipitation > 0.5:
        rating = "poor"
        notes.append(f"Rain ({precipitation:.1f} mm/hr) significantly reduces grip.")
    elif precipitation > 0:
        rating = "reduced"
        notes.append("Light precipitation — track may be damp.")

    if air_temp_c < 10:
        if rating == "good":
            rating = "reduced"
        notes.append(f"Cold conditions ({_c_to_f(air_temp_c):.0f} °F) — tires need more warm-up laps.")

    if air_temp_c > 35:
        notes.append("High air temp — engine may lose power from heat soak; stay hydrated.")
    elif air_temp_c < 5:
        notes.append("Very cold air — expect less tire grip until tires are up to temperature.")

    if humidity > 85:
        notes.append("High humidity reduces air density (slightly less engine power).")

    if not notes:
        notes.append("Conditions are favorable for good grip and consistent lap times.")

    return {"rating": rating, "notes": notes}


async def fetch_session_weather(
    latitude: float,
    longitude: float,
    session_date: str | date | None,
    session_hour: int | None = None,
) -> dict[str, Any] | None:
    """Fetch weather conditions for a session.

    Returns a dict with temperature, humidity, wind, precipitation, pressure,
    cloud cover, estimated track temp, and grip assessment.
    Returns None if weather data is unavailable.
    """
    if session_date is None:
        return None

    if isinstance(session_date, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                parsed_dt = datetime.strptime(session_date, fmt)
                target_date = parsed_dt.date()
                if session_hour is None and fmt.count(":") >= 1:
                    session_hour = parsed_dt.hour
                break
            except ValueError:
                continue
        else:
            logger.warning("Could not parse session date: %s", session_date)
            return None
    else:
        target_date = session_date

    date_str = target_date.isoformat()

    days_ago = (date.today() - target_date).days
    if days_ago < 0:
        days_ago = 0
    use_archive = days_ago > 5
    base_url = ARCHIVE_URL if use_archive else FORECAST_URL

    params: dict[str, Any] = {
        "latitude": round(latitude, 4),
        "longitude": round(longitude, 4),
        "hourly": ",".join(HOURLY_VARS),
        "start_date": date_str,
        "end_date": date_str,
        "timezone": "auto",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(base_url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("Failed to fetch weather from Open-Meteo: %s", e)
        return None

    hourly = data.get("hourly")
    if not hourly or not hourly.get("time"):
        return None

    if session_hour is not None:
        hour_idx = min(session_hour, len(hourly["time"]) - 1)
    else:
        hour_idx = 12  # default to midday

    def _val(key: str) -> float:
        values = hourly.get(key, [])
        if hour_idx < len(values) and values[hour_idx] is not None:
            return float(values[hour_idx])
        valid = [v for v in values if v is not None]
        return float(sum(valid) / len(valid)) if valid else 0.0

    air_temp_c = _val("temperature_2m")
    humidity = _val("relative_humidity_2m")
    wind_speed_kmh = _val("wind_speed_10m")
    wind_dir_deg = _val("wind_direction_10m")
    precipitation = _val("precipitation")
    pressure = _val("surface_pressure")
    cloud_cover = _val("cloud_cover")

    grip = _assess_grip_conditions(air_temp_c, humidity, precipitation)

    return {
        "air_temp_f": _c_to_f(air_temp_c),
        "air_temp_c": round(air_temp_c, 1),
        "humidity_pct": round(humidity, 1),
        "wind_speed_mph": _kmh_to_mph(wind_speed_kmh),
        "wind_speed_kmh": round(wind_speed_kmh, 1),
        "wind_direction_deg": round(wind_dir_deg, 1),
        "wind_direction_label": _wind_direction_label(wind_dir_deg),
        "precipitation_mm": round(precipitation, 2),
        "surface_pressure_hpa": round(pressure, 1),
        "cloud_cover_pct": round(cloud_cover, 1),
        "grip_assessment": grip,
        "source": "Open-Meteo",
        "conditions_label": _conditions_label(precipitation, cloud_cover),
    }


def _conditions_label(precip_mm: float, cloud_pct: float) -> str:
    if precip_mm > 2:
        return "Rainy"
    if precip_mm > 0.2:
        return "Light Rain"
    if cloud_pct > 80:
        return "Overcast"
    if cloud_pct > 50:
        return "Partly Cloudy"
    if cloud_pct > 20:
        return "Mostly Sunny"
    return "Clear / Sunny"
