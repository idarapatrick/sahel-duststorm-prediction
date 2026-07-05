"""
SahelDust Data Pipeline
Fetches real-time forecast data from Open-Meteo (atmospheric)
and Google Earth Engine (SMAP soil moisture, MODIS AOD).

Supports two modes:
1. Forecast mode: predicts dust events 24-72 hours ahead using forecast data
2. Historical mode: uses past observations for validation and demo

Open-Meteo provides atmospheric forecast data with no authentication required.
GEE provides SMAP and MODIS data with a 2-7 day lag.
"""

import asyncio
import json
import math
import numpy as np
import requests
from datetime import datetime, timedelta, timezone

try:
    import ee
    ee.Initialize(project='sahel-dust-forecasting')
    GEE_AVAILABLE = True
except Exception:
    GEE_AVAILABLE = False
    print("Google Earth Engine not available. Using Open-Meteo for all data.")


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

OPEN_METEO_VARS = [
    "wind_speed_10m",
    "wind_direction_10m",
    "temperature_2m",
    "surface_pressure",
    "boundary_layer_height",
    "precipitation",
    "dewpoint_2m",
    "soil_moisture_0_to_7cm",
]


def get_location_name(lat: float, lon: float) -> str:
    """Reverse geocode coordinates to a place name using OpenStreetMap Nominatim."""
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "lat": lat,
                "lon": lon,
                "format": "json",
                "zoom": 10,
                "accept-language": "en",
            },
            headers={"User-Agent": "SahelDust/1.0"},
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            address = data.get("address", {})
            city = (
                address.get("city")
                or address.get("town")
                or address.get("village")
                or address.get("county", "")
            )
            state = address.get("state", "")
            country = address.get("country", "")
            parts = [p for p in [city, state, country] if p]
            return ", ".join(parts) if parts else data.get("display_name", "Unknown")
        return "Unknown"
    except Exception:
        return "Unknown"


def _fetch_openmeteo_forecast(lat: float, lon: float, target_date: datetime) -> dict:
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    target_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    today_naive = today.replace(tzinfo=None)
    days_diff = (target_day - today_naive).days

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(OPEN_METEO_VARS),
        "timezone": "UTC",
        "wind_speed_unit": "ms",
        "precipitation_unit": "mm",
    }

    if days_diff < 0:
        params["past_days"] = min(abs(days_diff) + 4, 92)
        params["forecast_days"] = 1
    else:
        params["past_days"] = 3
        params["forecast_days"] = min(days_diff + 2, 16)

    response = requests.get(OPEN_METEO_URL, params=params, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"Open-Meteo API error: {response.status_code} {response.text}")

    return response.json()


def _extract_72h_window(data: dict, target_date: datetime) -> list:
    hourly = data["hourly"]
    times = hourly["time"]

    target_midnight = target_date.strftime("%Y-%m-%dT00:00")
    if target_midnight not in times:
        target_dt = datetime.strptime(target_midnight, "%Y-%m-%dT%H:%M")
        closest_idx = min(
            range(len(times)),
            key=lambda i: abs(datetime.strptime(times[i], "%Y-%m-%dT%H:%M") - target_dt),
        )
    else:
        closest_idx = times.index(target_midnight)

    start_idx = closest_idx - 60
    end_idx = closest_idx + 12

    if start_idx < 0 or end_idx > len(times):
        raise RuntimeError(
            f"Not enough data for 72-hour window. "
            f"Need indices {start_idx} to {end_idx}, have {len(times)} hours."
        )

    atmospheric = []
    for i in range(start_idx, end_idx):
        ws = hourly["wind_speed_10m"][i] or 0.0
        wd = hourly["wind_direction_10m"][i] or 0.0
        t2m = hourly["temperature_2m"][i] or 300.0
        sp = hourly["surface_pressure"][i] or 1000.0
        blh = hourly["boundary_layer_height"][i] or 500.0
        tp = hourly["precipitation"][i] or 0.0
        d2m = hourly["dewpoint_2m"][i] or 290.0

        wd_rad = math.radians(wd)
        u10 = -ws * math.sin(wd_rad)
        v10 = -ws * math.cos(wd_rad)
        t2m_kelvin = t2m + 273.15
        d2m_kelvin = d2m + 273.15
        sp_pa = sp * 100.0
        tp_m = tp / 1000.0

        atmospheric.append([u10, v10, t2m_kelvin, sp_pa, blh, tp_m, d2m_kelvin])

    return atmospheric


def _extract_soil_moisture(data: dict, target_date: datetime) -> float:
    hourly = data["hourly"]
    times = hourly["time"]

    target_morning = target_date.strftime("%Y-%m-%dT06:00")
    if target_morning in times:
        idx = times.index(target_morning)
        sm = hourly["soil_moisture_0_to_7cm"][idx]
        if sm is not None:
            return sm

    target_dt = datetime.strptime(target_date.strftime("%Y-%m-%dT06:00"), "%Y-%m-%dT%H:%M")
    for offset in range(0, 24):
        for direction in [1, -1]:
            check_time = (target_dt + timedelta(hours=offset * direction)).strftime("%Y-%m-%dT%H:%M")
            if check_time in times:
                idx = times.index(check_time)
                val = hourly["soil_moisture_0_to_7cm"][idx]
                if val is not None:
                    return val

    return 0.05


def _gee_grid_for_point(lat, lon):
    return {
        "dimensions": {"width": 1, "height": 1},
        "affineTransform": {
            "scaleX": 0.25, "shearX": 0, "translateX": lon - 0.125,
            "shearY": 0, "scaleY": -0.25, "translateY": lat + 0.125,
        },
        "crsCode": "EPSG:4326",
    }


def _fetch_smap_gee(lat, lon, date):
    if not GEE_AVAILABLE:
        return None, None

    grid = _gee_grid_for_point(lat, lon)
    date_naive = date.replace(tzinfo=None) if date.tzinfo else date

    coll_id = (
        "NASA/SMAP/SPL3SMP_E/005"
        if date_naive < datetime(2023, 12, 4)
        else "NASA/SMAP/SPL3SMP_E/006"
    )

    try:
        day_start = ee.Date(date_naive.strftime("%Y-%m-%d"))
        day_end = day_start.advance(1, "day")

        smap = (
            ee.ImageCollection(coll_id)
            .filterDate(day_start, day_end)
            .select(["soil_moisture_am", "vegetation_water_content_am"])
        )

        if smap.size().getInfo() == 0:
            return None, None

        img = smap.first()

        sm_pixels = ee.data.computePixels({
            "expression": img.select("soil_moisture_am"),
            "fileFormat": "NUMPY_NDARRAY",
            "grid": grid,
        })
        sm = float(sm_pixels["soil_moisture_am"][0][0])
        if sm < 0:
            sm = None

        vwc_pixels = ee.data.computePixels({
            "expression": img.select("vegetation_water_content_am"),
            "fileFormat": "NUMPY_NDARRAY",
            "grid": grid,
        })
        vwc = float(vwc_pixels["vegetation_water_content_am"][0][0])
        if vwc < 0:
            vwc = None

        return sm, vwc
    except Exception:
        return None, None


def _fetch_modis_aod_gee(lat, lon, date):
    if not GEE_AVAILABLE:
        return 0.0

    grid = _gee_grid_for_point(lat, lon)
    date_naive = date.replace(tzinfo=None) if date.tzinfo else date

    try:
        day_start = ee.Date(date_naive.strftime("%Y-%m-%d"))
        day_end = day_start.advance(1, "day")

        modis = (
            ee.ImageCollection("MODIS/061/MCD19A2_GRANULES")
            .filterDate(day_start, day_end)
            .select("Optical_Depth_055")
        )

        if modis.size().getInfo() == 0:
            return 0.0

        pixels = ee.data.computePixels({
            "expression": modis.max(),
            "fileFormat": "NUMPY_NDARRAY",
            "grid": grid,
        })

        raw = float(pixels["Optical_Depth_055"][0][0])
        if raw <= 0:
            return 0.0
        return raw * 0.001
    except Exception:
        return 0.0


async def fetch_features(lat: float, lon: float) -> tuple[list, list, str]:
    loop = asyncio.get_event_loop()

    for days_back in range(0, 11):
        date = datetime.now(timezone.utc) - timedelta(days=days_back)
        try:
            atmospheric, surface = await _build_features(lat, lon, date, loop)
            return atmospheric, surface, date.strftime("%Y-%m-%d")
        except RuntimeError:
            continue

    raise RuntimeError(
        f"Could not fetch data for {lat:.3f}N, {lon:.3f}E (checked last 10 days)"
    )


async def fetch_features_for_date(
    lat: float, lon: float, date: datetime
) -> tuple[list, list, str]:
    loop = asyncio.get_event_loop()
    atmospheric, surface = await _build_features(lat, lon, date, loop)
    return atmospheric, surface, date.strftime("%Y-%m-%d")


async def fetch_forecast(lat: float, lon: float, days_ahead: int = 3) -> list:
    loop = asyncio.get_event_loop()
    forecasts = []

    for day_offset in range(1, days_ahead + 1):
        target = datetime.now(timezone.utc) + timedelta(days=day_offset)
        try:
            atmospheric, surface = await _build_features(lat, lon, target, loop)
            forecasts.append({
                "date": target.strftime("%Y-%m-%d"),
                "atmospheric": atmospheric,
                "surface": surface,
            })
        except RuntimeError as e:
            forecasts.append({
                "date": target.strftime("%Y-%m-%d"),
                "error": str(e),
            })

    return forecasts


async def _build_features(lat, lon, date, loop):
    raw_data = await loop.run_in_executor(
        None, _fetch_openmeteo_forecast, lat, lon, date
    )
    atmospheric = _extract_72h_window(raw_data, date)

    sm = None
    vwc = 0.0

    if GEE_AVAILABLE:
        for smap_offset in range(0, 8):
            smap_date = date - timedelta(days=smap_offset)
            sm_try, vwc_try = await loop.run_in_executor(
                None, _fetch_smap_gee, lat, lon, smap_date
            )
            if sm_try is not None:
                sm = sm_try
                vwc = vwc_try if vwc_try is not None else 0.0
                break

    if sm is None:
        sm = _extract_soil_moisture(raw_data, date)
        vwc = 0.0

    prev_aod = 0.0
    if GEE_AVAILABLE:
        for aod_offset in range(1, 8):
            aod_date = date - timedelta(days=aod_offset)
            prev_aod = await loop.run_in_executor(
                None, _fetch_modis_aod_gee, lat, lon, aod_date
            )
            if prev_aod > 0:
                break

    month = date.month
    month_sin = float(np.sin(2 * np.pi * month / 12))
    month_cos = float(np.cos(2 * np.pi * month / 12))

    surface = [sm, vwc, prev_aod, lat, lon, month_sin, month_cos]

    return atmospheric, surface


def save_payload_for_swagger(lat, lon, date, filename="swagger_payload.json"):
    print(f"Fetching data for {lat:.3f}N, {lon:.3f}E on {date.strftime('%Y-%m-%d')}...")

    raw_data = _fetch_openmeteo_forecast(lat, lon, date)
    atmospheric = _extract_72h_window(raw_data, date)
    sm = _extract_soil_moisture(raw_data, date)

    vwc = 0.0
    prev_aod = 0.0

    if GEE_AVAILABLE:
        for offset in range(0, 8):
            sm_gee, vwc_gee = _fetch_smap_gee(lat, lon, date - timedelta(days=offset))
            if sm_gee is not None:
                sm = sm_gee
                vwc = vwc_gee if vwc_gee is not None else 0.0
                break

        for offset in range(1, 8):
            aod = _fetch_modis_aod_gee(lat, lon, date - timedelta(days=offset))
            if aod > 0:
                prev_aod = aod
                break

    month = date.month
    month_sin = float(np.sin(2 * np.pi * month / 12))
    month_cos = float(np.cos(2 * np.pi * month / 12))
    surface = [sm, vwc, prev_aod, lat, lon, month_sin, month_cos]

    payload = {"atmospheric": atmospheric, "surface": surface}

    with open(filename, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Saved: {filename}")
    return payload


if __name__ == "__main__":
    HF_API_URL = "https://mavencodes-saheldust-api.hf.space/predict"

    def predict_and_print(lat, lon, date, label=""):
        print(f"\n{label}")
        location = get_location_name(lat, lon)
        print(f"Location: {location} ({lat:.3f}N, {lon:.3f}E)")
        print(f"Date: {date.strftime('%Y-%m-%d')}")

        try:
            raw_data = _fetch_openmeteo_forecast(lat, lon, date)
            atmospheric = _extract_72h_window(raw_data, date)
            sm = _extract_soil_moisture(raw_data, date)
            print(f"Atmospheric: {len(atmospheric)} timesteps")
            print(f"Soil moisture: {sm:.4f}")
        except Exception as e:
            print(f"Failed: {e}")
            return

        vwc = 0.0
        prev_aod = 0.0

        if GEE_AVAILABLE:
            for offset in range(0, 8):
                smap_date = date - timedelta(days=offset)
                sm_gee, vwc_gee = _fetch_smap_gee(lat, lon, smap_date)
                if sm_gee is not None:
                    sm = sm_gee
                    vwc = vwc_gee if vwc_gee is not None else 0.0
                    print(f"SMAP soil moisture: {sm:.4f} ({offset} days ago)")
                    print(f"Vegetation water content: {vwc:.4f}")
                    break

            for offset in range(1, 8):
                aod = _fetch_modis_aod_gee(lat, lon, date - timedelta(days=offset))
                if aod > 0:
                    prev_aod = aod
                    print(f"Previous AOD: {prev_aod:.4f} ({offset} days ago)")
                    break

        month = date.month
        month_sin = float(np.sin(2 * np.pi * month / 12))
        month_cos = float(np.cos(2 * np.pi * month / 12))
        surface = [sm, vwc, prev_aod, lat, lon, month_sin, month_cos]

        payload = {"atmospheric": atmospheric, "surface": surface}

        print("Calling API...")
        try:
            response = requests.post(HF_API_URL, json=payload, timeout=30)
            result = response.json()
            print(f"Probability: {result['probability']:.4f}")
            print(f"Dust event: {result['dust_event']}")
            print(f"Risk level: {result['risk_level'].upper()}")
        except Exception as e:
            print(f"API error: {e}")

    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    day_after = datetime.now(timezone.utc) + timedelta(days=2)

    predict_and_print(13.529, 2.665, tomorrow, "Banizoumbou TOMORROW")
    predict_and_print(12.45, 4.20, tomorrow, "Birnin Kebbi TOMORROW")
    predict_and_print(14.394, -17.467, tomorrow, "Dakar TOMORROW")
    predict_and_print(12.364, -1.476, tomorrow, "Ouagadougou TOMORROW")

    save_payload_for_swagger(13.529, 2.665, tomorrow,
                             filename="swagger_banizoumbou_forecast.json")
    save_payload_for_swagger(12.364, -1.476, tomorrow,
                             filename="swagger_ouagadougou_forecast.json")

    print("\nDone.")