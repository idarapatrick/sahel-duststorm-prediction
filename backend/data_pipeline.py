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

# GEE is optional. If not available, surface features use Open-Meteo soil data.
try:
    import ee
    ee.Initialize(project='sahel-dust-forecasting')
    GEE_AVAILABLE = True
except Exception:
    GEE_AVAILABLE = False
    print("WARNING: Google Earth Engine not available. Using Open-Meteo for all data.")


# OPEN-METEO: ATMOSPHERIC FORECAST + SOIL MOISTURE
# Free, no auth, JSON, real-time + forecast up to 16 days

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Open-Meteo variable names mapped to our model's 7 variables
# Our model expects: u10, v10, t2m, sp, blh, tp, d2m
# Open-Meteo provides wind as speed+direction, we convert to u/v components

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


def _fetch_openmeteo_forecast(lat: float, lon: float, target_date: datetime) -> dict:
    """
    Fetch hourly forecast/historical data from Open-Meteo.
    Returns raw JSON response with all needed variables.
    """
    # Calculate how many past and future days we need
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    target_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    days_diff = (target_day - today).days

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(OPEN_METEO_VARS),
        "timezone": "UTC",
        "wind_speed_unit": "ms",
        "precipitation_unit": "mm",
    }

    # If target is in the past, use past_days parameter
    if days_diff < 0:
        params["past_days"] = min(abs(days_diff) + 4, 92)
        params["forecast_days"] = 1
    else:
        # For future dates, request enough forecast days
        params["past_days"] = 3
        params["forecast_days"] = min(days_diff + 2, 16)

    response = requests.get(OPEN_METEO_URL, params=params, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"Open-Meteo API error: {response.status_code} {response.text}")

    return response.json()


def _extract_72h_window(data: dict, target_date: datetime) -> list:
    """
    Extract the 72-hour atmospheric window (T-60 to T+12) from Open-Meteo data.
    Converts wind speed + direction to u10, v10 components.
    Returns list of 72 sublists, each with 7 values.
    """
    hourly = data["hourly"]
    times = hourly["time"]

    # Find the target midnight index
    target_midnight = target_date.strftime("%Y-%m-%dT00:00")
    if target_midnight not in times:
        # Find the closest available time
        target_dt = datetime.strptime(target_midnight, "%Y-%m-%dT%H:%M")
        closest_idx = min(range(len(times)),
                         key=lambda i: abs(datetime.strptime(times[i], "%Y-%m-%dT%H:%M") - target_dt))
    else:
        closest_idx = times.index(target_midnight)

    # Window: T-60 to T+12 relative to midnight
    start_idx = closest_idx - 60
    end_idx = closest_idx + 12

    if start_idx < 0 or end_idx > len(times):
        raise RuntimeError(
            f"Not enough data for 72-hour window. "
            f"Need indices {start_idx} to {end_idx}, have {len(times)} hours."
        )

    atmospheric = []
    for i in range(start_idx, end_idx):
        ws = hourly["wind_speed_10m"][i]
        wd = hourly["wind_direction_10m"][i]
        t2m = hourly["temperature_2m"][i]
        sp = hourly["surface_pressure"][i]
        blh = hourly["boundary_layer_height"][i]
        tp = hourly["precipitation"][i]
        d2m = hourly["dewpoint_2m"][i]

        # Handle None values (missing data)
        ws = ws if ws is not None else 0.0
        wd = wd if wd is not None else 0.0
        t2m = t2m if t2m is not None else 300.0
        sp = sp if sp is not None else 1000.0
        blh = blh if blh is not None else 500.0
        tp = tp if tp is not None else 0.0
        d2m = d2m if d2m is not None else 290.0

        # Convert wind speed + direction to u10, v10 components
        # u10 = eastward component, v10 = northward component
        wd_rad = math.radians(wd)
        u10 = -ws * math.sin(wd_rad)
        v10 = -ws * math.cos(wd_rad)

        # Convert Open-Meteo units to ERA5 units
        # Temperature: Open-Meteo gives Celsius, ERA5 uses Kelvin
        t2m_kelvin = t2m + 273.15
        d2m_kelvin = d2m + 273.15
        # Pressure: Open-Meteo gives hPa, ERA5 uses Pa
        sp_pa = sp * 100.0
        # Precipitation: Open-Meteo gives mm, ERA5 uses metres
        tp_m = tp / 1000.0

        atmospheric.append([u10, v10, t2m_kelvin, sp_pa, blh, tp_m, d2m_kelvin])

    return atmospheric


def _extract_soil_moisture(data: dict, target_date: datetime) -> float:
    """
    Extract soil moisture value for the target date morning from Open-Meteo.
    Uses the 06:00 UTC value to match SMAP AM overpass timing.
    """
    hourly = data["hourly"]
    times = hourly["time"]

    target_morning = target_date.strftime("%Y-%m-%dT06:00")
    if target_morning in times:
        idx = times.index(target_morning)
        sm = hourly["soil_moisture_0_to_7cm"][idx]
        if sm is not None:
            return sm

    # Fallback: use the closest available value
    target_dt = datetime.strptime(target_date.strftime("%Y-%m-%dT06:00"), "%Y-%m-%dT%H:%M")
    for offset in range(0, 24):
        for direction in [1, -1]:
            check_time = (target_dt + timedelta(hours=offset * direction)).strftime("%Y-%m-%dT%H:%M")
            if check_time in times:
                idx = times.index(check_time)
                val = hourly["soil_moisture_0_to_7cm"][idx]
                if val is not None:
                    return val

    return 0.05  # default if nothing found


# GOOGLE EARTH ENGINE: SMAP + MODIS (with lag, for validation)

def _gee_grid_for_point(lat, lon):
    return {
        'dimensions': {'width': 1, 'height': 1},
        'affineTransform': {
            'scaleX': 0.25, 'shearX': 0, 'translateX': lon - 0.125,
            'shearY': 0, 'scaleY': -0.25, 'translateY': lat + 0.125
        },
        'crsCode': 'EPSG:4326'
    }


def _fetch_smap_gee(lat, lon, date):
    """Fetch SMAP soil moisture and vegetation water content from GEE."""
    if not GEE_AVAILABLE:
        return None, None

    grid = _gee_grid_for_point(lat, lon)

    coll_id = ('NASA/SMAP/SPL3SMP_E/005'
               if date < datetime(2023, 12, 4)
               else 'NASA/SMAP/SPL3SMP_E/006')

    try:
        day_start = ee.Date(date.strftime('%Y-%m-%d'))
        day_end = day_start.advance(1, 'day')

        smap = (ee.ImageCollection(coll_id)
                  .filterDate(day_start, day_end)
                  .select(['soil_moisture_am', 'vegetation_water_content_am']))

        if smap.size().getInfo() == 0:
            return None, None

        img = smap.first()

        sm_pixels = ee.data.computePixels({
            'expression': img.select('soil_moisture_am'),
            'fileFormat': 'NUMPY_NDARRAY',
            'grid': grid
        })
        sm = float(sm_pixels['soil_moisture_am'][0][0])
        if sm < 0:
            sm = None

        vwc_pixels = ee.data.computePixels({
            'expression': img.select('vegetation_water_content_am'),
            'fileFormat': 'NUMPY_NDARRAY',
            'grid': grid
        })
        vwc = float(vwc_pixels['vegetation_water_content_am'][0][0])
        if vwc < 0:
            vwc = None

        return sm, vwc
    except Exception:
        return None, None


def _fetch_modis_aod_gee(lat, lon, date):
    """Fetch MODIS AOD from GEE."""
    if not GEE_AVAILABLE:
        return 0.0

    grid = _gee_grid_for_point(lat, lon)

    try:
        day_start = ee.Date(date.strftime('%Y-%m-%d'))
        day_end = day_start.advance(1, 'day')

        modis = (ee.ImageCollection('MODIS/061/MCD19A2_GRANULES')
                   .filterDate(day_start, day_end)
                   .select('Optical_Depth_055'))

        if modis.size().getInfo() == 0:
            return 0.0

        pixels = ee.data.computePixels({
            'expression': modis.max(),
            'fileFormat': 'NUMPY_NDARRAY',
            'grid': grid
        })

        raw = float(pixels['Optical_Depth_055'][0][0])
        if raw <= 0:
            return 0.0
        return raw * 0.001
    except Exception:
        return 0.0


# PUBLIC API: fetch_features and fetch_features_for_date

async def fetch_features(lat: float, lon: float) -> tuple[list, list, str]:
    """
    Fetch features for prediction using the most recent available data.
    Uses Open-Meteo for atmospheric data (available in real-time).
    Uses GEE for SMAP and MODIS (with fallback for lag).

    Returns:
        atmospheric: 72x7 list
        surface: 7-element list
        prediction_date: YYYY-MM-DD string
    """
    loop = asyncio.get_event_loop()

    # Try dates from today backwards until we find available data
    for days_back in range(0, 11):
        date = datetime.utcnow() - timedelta(days=days_back)
        try:
            atmospheric, surface = await _build_features(lat, lon, date, loop)
            return atmospheric, surface, date.strftime('%Y-%m-%d')
        except RuntimeError:
            continue

    raise RuntimeError(
        f"Could not fetch data for {lat:.3f}N, {lon:.3f}E (checked last 10 days)"
    )


async def fetch_features_for_date(lat: float, lon: float, date: datetime) -> tuple[list, list, str]:
    """
    Fetch features for a specific date. Works for both past dates
    and future dates (up to 10 days ahead using forecast data).
    """
    loop = asyncio.get_event_loop()
    atmospheric, surface = await _build_features(lat, lon, date, loop)
    return atmospheric, surface, date.strftime('%Y-%m-%d')


async def fetch_forecast(lat: float, lon: float, days_ahead: int = 3) -> list:
    """
    Fetch predictions for the next N days.
    Returns a list of dicts with date, atmospheric, and surface features
    for each day. Used by the progressive alert system.
    """
    loop = asyncio.get_event_loop()
    forecasts = []

    for day_offset in range(1, days_ahead + 1):
        target = datetime.utcnow() + timedelta(days=day_offset)
        try:
            atmospheric, surface = await _build_features(lat, lon, target, loop)
            forecasts.append({
                "date": target.strftime('%Y-%m-%d'),
                "atmospheric": atmospheric,
                "surface": surface,
            })
        except RuntimeError as e:
            forecasts.append({
                "date": target.strftime('%Y-%m-%d'),
                "error": str(e),
            })

    return forecasts


async def _build_features(lat, lon, date, loop):
    """
    Build the atmospheric and surface feature arrays for a given date.
    Atmospheric: from Open-Meteo (real-time forecast or recent historical).
    Surface: SMAP from GEE with Open-Meteo soil moisture fallback.
    """
    # Fetch atmospheric data from Open-Meteo (runs in thread pool)
    raw_data = await loop.run_in_executor(
        None, _fetch_openmeteo_forecast, lat, lon, date
    )
    atmospheric = _extract_72h_window(raw_data, date)

    # Soil moisture: try GEE SMAP first, fall back to Open-Meteo
    sm = None
    vwc = 0.0

    if GEE_AVAILABLE:
        # Try SMAP from GEE (may have 2-7 day lag)
        for smap_offset in range(0, 8):
            smap_date = date - timedelta(days=smap_offset)
            sm_try, vwc_try = await loop.run_in_executor(
                None, _fetch_smap_gee, lat, lon, smap_date
            )
            if sm_try is not None:
                sm = sm_try
                vwc = vwc_try if vwc_try is not None else 0.0
                break

    # Fallback: use Open-Meteo soil moisture
    if sm is None:
        sm = _extract_soil_moisture(raw_data, date)
        vwc = 0.0  # Open-Meteo does not provide vegetation water content

    # Previous day AOD: try GEE MODIS
    prev_aod = 0.0
    if GEE_AVAILABLE:
        for aod_offset in range(1, 8):
            aod_date = date - timedelta(days=aod_offset)
            prev_aod = await loop.run_in_executor(
                None, _fetch_modis_aod_gee, lat, lon, aod_date
            )
            if prev_aod > 0:
                break

    # Build surface feature vector
    month = date.month
    month_sin = float(np.sin(2 * np.pi * month / 12))
    month_cos = float(np.cos(2 * np.pi * month / 12))

    surface = [sm, vwc, prev_aod, lat, lon, month_sin, month_cos]

    return atmospheric, surface


# SWAGGER PAYLOAD GENERATOR

def save_payload_for_swagger(lat, lon, date, filename="swagger_payload.json"):
    """Generate a JSON payload file for testing the API via Swagger UI."""
    print(f"\nFetching data for Swagger payload...")
    print(f"  Location: {lat:.3f}N, {lon:.3f}E")
    print(f"  Date: {date.strftime('%Y-%m-%d')}")

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

    with open(filename, 'w') as f:
        json.dump(payload, f, indent=2)

    print(f"  Saved: {filename}")
    print(f"  sm={sm:.4f}, vwc={vwc:.4f}, prev_aod={prev_aod:.4f}")
    return payload


# STANDALONE MODE

if __name__ == "__main__":
    import httpx

    HF_API_URL = "https://mavencodes-saheldust-api.hf.space/predict"

    def predict_and_print(lat, lon, date, label=""):
        print(f"\n{'='*55}")
        if label:
            print(f"  {label}")
        print(f"  Location: {lat:.3f}N, {lon:.3f}E")
        print(f"  Date: {date.strftime('%Y-%m-%d')}")
        print(f"{'='*55}")

        try:
            raw_data = _fetch_openmeteo_forecast(lat, lon, date)
            atmospheric = _extract_72h_window(raw_data, date)
            sm = _extract_soil_moisture(raw_data, date)
            print(f"  Atmospheric: {len(atmospheric)} timesteps")
            print(f"  Soil moisture (Open-Meteo): {sm:.4f}")
        except Exception as e:
            print(f"  FAILED: {e}")
            return

        vwc = 0.0
        prev_aod = 0.0

        if GEE_AVAILABLE:
            for offset in range(0, 8):
                sm_gee, vwc_gee = _fetch_smap_gee(lat, lon, date - timedelta(days=offset))
                if sm_gee is not None:
                    sm = sm_gee
                    vwc = vwc_gee if vwc_gee is not None else 0.0
                    print(f"  SMAP soil moisture: {sm:.4f} ({offset} days ago)")
                    print(f"  Vegetation water content: {vwc:.4f}")
                    break

            for offset in range(1, 8):
                aod = _fetch_modis_aod_gee(lat, lon, date - timedelta(days=offset))
                if aod > 0:
                    prev_aod = aod
                    print(f"  Previous AOD: {prev_aod:.4f} ({offset} days ago)")
                    break

        month = date.month
        month_sin = float(np.sin(2 * np.pi * month / 12))
        month_cos = float(np.cos(2 * np.pi * month / 12))
        surface = [sm, vwc, prev_aod, lat, lon, month_sin, month_cos]

        payload = {"atmospheric": atmospheric, "surface": surface}

        print(f"Making Calls to API...")
        try:
            response = requests.post(HF_API_URL, json=payload, timeout=30)
            result = response.json()
            print(f"\n  RESULT:")
            print(f"    Probability: {result['probability']:.4f}")
            print(f"    Dust event:  {result['dust_event']}")
            print(f"    Risk level:  {result['risk_level'].upper()}")
        except Exception as e:
            print(f"  API ERROR: {e}")

    # FORECAST PREDICTIONS (future dates using Open-Meteo forecast)
    print("  FORECAST PREDICTIONS (next 3 days)")

    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    day_after = datetime.now(timezone.utc) + timedelta(days=2)
    three_days = datetime.now(timezone.utc) + timedelta(days=3)

    predict_and_print(13.529, 2.665, tomorrow, "Banizoumbou TOMORROW")
    predict_and_print(13.529, 2.665, day_after, "Banizoumbou DAY AFTER")
    predict_and_print(13.529, 2.665, three_days, "Banizoumbou 3 DAYS OUT")

    predict_and_print(12.45, 4.20, tomorrow, "Birnin Kebbi TOMORROW")
    predict_and_print(14.394, -17.467, tomorrow, "Dakar TOMORROW")
    predict_and_print(12.364, -1.476, tomorrow, "Ouagadougou TOMORROW")

    # HISTORICAL PREDICTIONS (past dates for validation)
    print("  HISTORICAL PREDICTIONS (past dates)")

    predict_and_print(13.529, 2.665, datetime(2024, 3, 15, tzinfo=timezone.utc), "Banizoumbou March 2024 (dry)")
    predict_and_print(13.529, 2.665, datetime(2024, 8, 15, tzinfo=timezone.utc), "Banizoumbou August 2024 (wet)")

    # GENERATE SWAGGER PAYLOADS
    print("\n")
    print(" GENERATING SWAGGER PAYLOADS")

    save_payload_for_swagger(13.529, 2.665, tomorrow,
                             filename="swagger_banizoumbou_forecast.json")
    save_payload_for_swagger(12.364, -1.476, tomorrow,
                             filename="swagger_ouagadougou_forecast.json")

    print("\nDone.")