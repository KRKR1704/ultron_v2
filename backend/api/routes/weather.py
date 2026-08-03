"""
api/routes/weather.py — GET /weather?lat={lat}&lon={lon}

Real current weather via Open-Meteo (https://open-meteo.com) — free, no
API key or signup required. The location display name comes from
BigDataCloud's free reverse-geocoding endpoint (also no key required);
if that lookup fails for any reason, the coordinates themselves are used
as the label so the endpoint never fails just because a friendly place
name couldn't be resolved.
"""

import logging

import httpx
from fastapi import APIRouter, HTTPException, Query

from api.models import WeatherResponse

log = logging.getLogger(__name__)
router = APIRouter()

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_REVERSE_GEOCODE_URL = "https://api.bigdatacloud.net/data/reverse-geocode-client"

# WMO weather interpretation codes (returned by Open-Meteo's current_weather)
# mapped to the UI's five condition buckets.
_WEATHERCODE_TO_CONDITION: dict[int, str] = {
    0: "sunny", 1: "sunny",
    2: "cloudy", 3: "cloudy", 45: "cloudy", 48: "cloudy",
    51: "rainy", 53: "rainy", 55: "rainy", 56: "rainy", 57: "rainy",
    61: "rainy", 63: "rainy", 65: "rainy", 66: "rainy", 67: "rainy",
    80: "rainy", 81: "rainy", 82: "rainy",
    71: "snowy", 73: "snowy", 75: "snowy", 77: "snowy", 85: "snowy", 86: "snowy",
    95: "rainy", 96: "rainy", 99: "rainy",
}
_WINDY_THRESHOLD_KMH = 30.0


def _condition_from(weathercode: int, windspeed_kmh: float) -> str:
    """Wind speed overrides the weather-code mapping above a gusty threshold."""
    if windspeed_kmh >= _WINDY_THRESHOLD_KMH:
        return "windy"
    return _WEATHERCODE_TO_CONDITION.get(weathercode, "cloudy")


async def _reverse_geocode(lat: float, lon: float) -> str:
    """Best-effort place name lookup — never raises, falls back to coordinates."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                _REVERSE_GEOCODE_URL,
                params={"latitude": lat, "longitude": lon, "localityLanguage": "en"},
            )
            resp.raise_for_status()
            data = resp.json()

        city = data.get("city") or data.get("locality")
        country = data.get("countryName")
        if city and country:
            return f"{city}, {country}"
        if city:
            return city
        if country:
            return country

    except Exception as err:
        log.warning("Reverse geocoding failed (%s) — falling back to coordinates.", err)

    return f"{lat:.2f}, {lon:.2f}"


@router.get("/weather", response_model=WeatherResponse)
async def get_weather(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _OPEN_METEO_URL,
                params={"latitude": lat, "longitude": lon, "current_weather": "true"},
            )
            resp.raise_for_status()
            current = resp.json()["current_weather"]

    except Exception as err:
        log.error("Open-Meteo request failed: %s", err)
        raise HTTPException(status_code=502, detail="Weather service unavailable.")

    location_name = await _reverse_geocode(lat, lon)

    return WeatherResponse(
        temperature=current["temperature"],
        condition=_condition_from(current["weathercode"], current["windspeed"]),
        location_name=location_name,
        unit="celsius",
    )
