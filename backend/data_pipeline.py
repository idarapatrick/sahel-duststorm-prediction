"""Build the deployed model's atmospheric and surface input payload.

Open-Meteo supplies modelled atmospheric fields, Earth Engine supplies delayed
SMAP and MODIS observations, and CAMS supplies an aerosol analysis fallback.
The module preserves provider provenance and never describes elapsed forecast
hours as measurements merely because their timestamps are now in the past.
"""

import asyncio
import json
import math
import os
import numpy as np
import requests
from datetime import datetime, timedelta, timezone

try:
    import ee
    from google.oauth2 import service_account

    gee_project = os.getenv("GEE_PROJECT_ID", "sahel-dust-forecasting").strip()
    gee_credentials_json = os.getenv("GEE_SERVICE_ACCOUNT_JSON", "").strip()
    if gee_credentials_json:
        credentials_info = json.loads(gee_credentials_json)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=[
                "https://www.googleapis.com/auth/earthengine",
                "https://www.googleapis.com/auth/cloud-platform",
            ],
        )
        ee.Initialize(credentials=credentials, project=gee_project)
    else:
        # Supports local `earthengine authenticate` and Render secret files via
        # GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/<filename>.json.
        ee.Initialize(project=gee_project)
    GEE_AVAILABLE = True
except Exception as exc:
    GEE_AVAILABLE = False
    print(f"Google Earth Engine not available ({type(exc).__name__}). Using satellite fallbacks.")


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

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

CURRENT_WEATHER_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "dew_point_2m",
    "precipitation",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "visibility",
    "cloud_cover",
    "soil_moisture_0_to_7cm",
]


def _fetch_openmeteo_current(lat: float, lon: float) -> dict:
    """Fetch the nearest current weather-model timestep from Open-Meteo."""
    response = requests.get(
        OPEN_METEO_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": ",".join(CURRENT_WEATHER_VARS),
            "timezone": "UTC",
            "wind_speed_unit": "ms",
            "precipitation_unit": "mm",
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Open-Meteo current conditions error: {response.status_code} {response.text}"
        )
    payload = response.json()
    current = payload.get("current")
    if not current:
        raise RuntimeError("Open-Meteo response did not contain current conditions")
    wind_ms = float(current.get("wind_speed_10m") or 0.0)
    return {
        "observed_at": current.get("time"),
        "interval_seconds": current.get("interval"),
        "temperature_c": current.get("temperature_2m"),
        "relative_humidity_pct": current.get("relative_humidity_2m"),
        "apparent_temperature_c": current.get("apparent_temperature"),
        "dewpoint_c": current.get("dew_point_2m"),
        "precipitation_mm": current.get("precipitation"),
        "surface_pressure_hpa": current.get("surface_pressure"),
        "wind_speed_ms": round(wind_ms, 2),
        "wind_speed_kmh": round(wind_ms * 3.6, 1),
        "wind_direction_deg": current.get("wind_direction_10m"),
        "wind_gusts_ms": current.get("wind_gusts_10m"),
        "visibility_m": current.get("visibility"),
        "cloud_cover_pct": current.get("cloud_cover"),
        "soil_moisture": current.get("soil_moisture_0_to_7cm"),
        "source": "open-meteo-current",
    }


def _fetch_cams_aod(lat: float, lon: float) -> tuple[float, str | None]:
    """Return the latest valid CAMS global AOD analysis or forecast.

    The CAMS ``current`` object can briefly be empty while a new model cycle is
    being published. Requesting the hourly series as well lets SahelWatch use
    the most recent valid value from the preceding 72 hours instead of storing
    a missing observation as a measured AOD of zero.
    """
    try:
        response = requests.get(
            OPEN_METEO_AIR_QUALITY_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "aerosol_optical_depth",
                "hourly": "aerosol_optical_depth",
                "domains": "cams_global",
                "past_days": 3,
                "forecast_days": 1,
                "timezone": "UTC",
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        current = payload.get("current") or {}
        value = current.get("aerosol_optical_depth")
        if value is not None and float(value) >= 0:
            observed_at = current.get("time")
            timestamp = (
                f"{observed_at}:00Z"
                if observed_at and len(observed_at) == 16
                else observed_at
            )
            return float(value), timestamp

        hourly = payload.get("hourly") or {}
        times = hourly.get("time") or []
        values = hourly.get("aerosol_optical_depth") or []
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        for observed_at, hourly_value in reversed(list(zip(times, values))):
            if hourly_value is None or float(hourly_value) < 0:
                continue
            observed_time = datetime.fromisoformat(observed_at)
            if observed_time <= now_naive:
                return float(hourly_value), f"{observed_at}:00Z"
        return 0.0, None
    except Exception as exc:
        print(f"CAMS AOD lookup failed for {lat:.3f},{lon:.3f}: {type(exc).__name__}")
        return 0.0, None


async def fetch_current_conditions(lat: float, lon: float) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _fetch_openmeteo_current, lat, lon)


def get_location_name(lat: float, lon: float) -> str:
    """Reverse geocode coordinates to a place name using OpenStreetMap Nominatim."""
    try:
        from coverage_store import nearest_covered_place

        nearest = nearest_covered_place(lat, lon)
        if nearest and abs(float(nearest.get("forecast_lat", nearest["lat"])) - lat) <= 0.08 \
                and abs(float(nearest.get("forecast_lon", nearest["lon"])) - lon) <= 0.08:
            return f"{nearest['name']}, {nearest['country']}"
    except Exception:
        # Reverse geocoding remains available during migration or database outages.
        pass
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

    # MODIS supervision is daily, so every feature window remains aligned to
    # the target calendar day's midnight.
    target_hour = target_date.strftime("%Y-%m-%dT00:00")
    if target_hour not in times:
        target_dt = datetime.strptime(target_hour, "%Y-%m-%dT%H:%M")
        closest_idx = min(
            range(len(times)),
            key=lambda i: abs(datetime.strptime(times[i], "%Y-%m-%dT%H:%M") - target_dt),
        )
    else:
        closest_idx = times.index(target_hour)

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


def _extract_72h_series(
    data: dict, target_date: datetime, atmospheric: list | None = None
) -> dict[str, list]:
    """Return the timestamped Open-Meteo values represented in the model tensor."""
    hourly = data["hourly"]
    times = hourly.get("time")
    if not times and atmospheric is not None:
        window_start = target_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(hours=60)
        timestamps = [
            (window_start + timedelta(hours=offset)).strftime(
                "%Y-%m-%dT%H:%M:00Z"
            )
            for offset in range(len(atmospheric))
        ]
        return {
            "timestamps": timestamps,
            "wind_speed_10m": [
                math.hypot(row[0], row[1]) for row in atmospheric
            ],
            "wind_direction_10m": [None for _ in atmospheric],
            "temperature_2m": [row[2] - 273.15 for row in atmospheric],
            "surface_pressure": [row[3] / 100 for row in atmospheric],
            "boundary_layer_height": [row[4] for row in atmospheric],
            "precipitation": [row[5] * 1000 for row in atmospheric],
            "dewpoint_2m": [row[6] - 273.15 for row in atmospheric],
        }
    if not times:
        raise RuntimeError("The Open-Meteo response has no hourly timestamps")
    target_hour = target_date.strftime("%Y-%m-%dT00:00")
    if target_hour in times:
        closest_idx = times.index(target_hour)
    else:
        target_dt = datetime.strptime(target_hour, "%Y-%m-%dT%H:%M")
        closest_idx = min(
            range(len(times)),
            key=lambda i: abs(
                datetime.strptime(times[i], "%Y-%m-%dT%H:%M") - target_dt
            ),
        )
    start_idx = closest_idx - 60
    end_idx = closest_idx + 12
    if start_idx < 0 or end_idx > len(times):
        raise RuntimeError("The Open-Meteo response does not contain the 72-hour window")
    names = (
        "wind_speed_10m",
        "wind_direction_10m",
        "temperature_2m",
        "surface_pressure",
        "boundary_layer_height",
        "precipitation",
        "dewpoint_2m",
    )
    return {
        "timestamps": [f"{value}:00Z" for value in times[start_idx:end_idx]],
        **{
            name: hourly[name][start_idx:end_idx]
            for name in names
        },
    }


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

        # A city point can fall on a masked satellite pixel. Average the nearby
        # 25 km area, which matches the broad spatial scale of the forecast.
        region = ee.Geometry.Point([lon, lat]).buffer(25_000)
        values = smap.first().reduceRegion(
            reducer=ee.Reducer.mean(), geometry=region, scale=9_000,
            bestEffort=True, maxPixels=100_000,
        ).getInfo()
        raw_sm = values.get("soil_moisture_am")
        raw_vwc = values.get("vegetation_water_content_am")
        sm = float(raw_sm) if raw_sm is not None and float(raw_sm) >= 0 else None
        vwc = float(raw_vwc) if raw_vwc is not None and float(raw_vwc) >= 0 else None

        return sm, vwc
    except Exception as exc:
        print(f"SMAP lookup failed for {lat:.3f},{lon:.3f} on {date_naive:%Y-%m-%d}: {type(exc).__name__}")
        return None, None


def _fetch_modis_aod_gee(lat, lon, date):
    if not GEE_AVAILABLE:
        return None

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
            return None

        # MODIS AOD is frequently cloud or quality masked at a single point.
        # Use the mean valid reading within 25 km of the forecast grid point.
        region = ee.Geometry.Point([lon, lat]).buffer(25_000)
        values = modis.max().reduceRegion(
            reducer=ee.Reducer.mean(), geometry=region, scale=1_000,
            bestEffort=True, maxPixels=1_000_000,
        ).getInfo()
        value = values.get("Optical_Depth_055")
        if value is None:
            return None
        raw = float(value)
        if raw <= 0:
            return None
        return raw * 0.001
    except Exception as exc:
        print(f"MODIS AOD lookup failed for {lat:.3f},{lon:.3f} on {date_naive:%Y-%m-%d}: {type(exc).__name__}")
        return None


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


async def fetch_features_detailed(lat: float, lon: float) -> tuple[list, list, str, dict]:
    """Fetch model inputs with field-level source, timestamp and missingness."""
    loop = asyncio.get_event_loop()
    for days_back in range(0, 11):
        date = datetime.now(timezone.utc) - timedelta(days=days_back)
        try:
            atmospheric, surface, provenance = await _build_features_with_provenance(lat, lon, date, loop)
            return atmospheric, surface, date.strftime("%Y-%m-%d"), provenance
        except RuntimeError:
            continue
    raise RuntimeError(f"Could not fetch data for {lat:.3f}N, {lon:.3f}E (checked last 10 days)")


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
    atmospheric, surface, _ = await _build_features_with_provenance(lat, lon, date, loop)
    return atmospheric, surface


async def _build_features_with_provenance(lat, lon, date, loop):
    atmospheric, surface, provenance, _ = await build_prediction_inputs(
        lat, lon, date, loop
    )
    return atmospheric, surface, provenance


async def build_prediction_inputs(lat, lon, date, loop=None):
    """Build one canonical model payload and return its raw source data.

    This public function is shared by central monitoring and payload-export
    paths so satellite fallback and provenance behaviour cannot
    silently diverge between callers.
    """
    loop = loop or asyncio.get_running_loop()
    retrieved_at = datetime.now(timezone.utc)
    raw_data = await loop.run_in_executor(
        None, _fetch_openmeteo_forecast, lat, lon, date
    )
    atmospheric = _extract_72h_window(raw_data, date)

    sm = None
    vwc = 0.0
    smap_observed_at = None
    sm_source = "open-meteo-forecast"
    vwc_available = False

    if GEE_AVAILABLE:
        for smap_offset in range(0, 8):
            smap_date = date - timedelta(days=smap_offset)
            sm_try, vwc_try = await loop.run_in_executor(
                None, _fetch_smap_gee, lat, lon, smap_date
            )
            if sm_try is not None:
                sm = sm_try
                vwc = vwc_try if vwc_try is not None else 0.0
                smap_observed_at = smap_date.strftime("%Y-%m-%d")
                sm_source = "smap"
                vwc_available = vwc_try is not None
                break

    if sm is None:
        sm = _extract_soil_moisture(raw_data, date)
        vwc = 0.0

    prev_aod = 0.0
    aod_observed_at = None
    aod_source = None
    if GEE_AVAILABLE:
        for aod_offset in range(1, 8):
            aod_date = date - timedelta(days=aod_offset)
            prev_aod = await loop.run_in_executor(
                None, _fetch_modis_aod_gee, lat, lon, aod_date
            )
            if prev_aod is not None and prev_aod > 0:
                aod_observed_at = aod_date.strftime("%Y-%m-%d")
                aod_source = "modis"
                break
    if aod_observed_at is None:
        prev_aod, aod_observed_at = await loop.run_in_executor(
            None, _fetch_cams_aod, lat, lon
        )
        if aod_observed_at is not None:
            aod_source = "cams-global"

    month = date.month
    month_sin = float(np.sin(2 * np.pi * month / 12))
    month_cos = float(np.cos(2 * np.pi * month / 12))

    surface = [sm, vwc, prev_aod, lat, lon, month_sin, month_cos]

    target_midnight = date.replace(hour=0, minute=0, second=0, microsecond=0)
    if target_midnight.tzinfo is None:
        target_midnight = target_midnight.replace(tzinfo=timezone.utc)
    provenance = {
        "retrieved_at": retrieved_at.isoformat(),
        "atmospheric": {
            "source": "open-meteo-forecast",
            "reference_date": date.strftime("%Y-%m-%d"),
            "available": True,
            "available_at": retrieved_at.isoformat(),
            "availability_is_estimated": True,
            "kind": "forecast",
            "forecast_target_at": target_midnight.isoformat(),
            "series": _extract_72h_series(raw_data, date, atmospheric),
        },
        "soil_moisture": {
            "source": sm_source,
            "observed_at": smap_observed_at,
            "available_at": retrieved_at.isoformat(),
            "availability_is_estimated": True,
            "available": sm is not None,
            "kind": "delayed_observation" if sm_source == "smap" else "forecast",
            "is_fallback": sm_source != "smap",
            "forecast_target_at": target_midnight.isoformat() if sm_source != "smap" else None,
        },
        "vegetation_water_content": {
            "source": "smap" if vwc_available else None,
            "observed_at": smap_observed_at if vwc_available else None,
            "available_at": retrieved_at.isoformat(),
            "availability_is_estimated": True,
            "available": vwc_available,
            "kind": "delayed_observation" if vwc_available else "missing",
            "is_fallback": False,
        },
        "previous_day_aod": {
            "source": aod_source,
            "observed_at": aod_observed_at,
            "available_at": retrieved_at.isoformat(),
            "availability_is_estimated": True,
            "available": aod_observed_at is not None,
            "kind": "delayed_observation" if aod_source == "modis" else "analysis" if aod_source else "missing",
            "is_fallback": aod_source == "cams-global",
        },
    }
    provenance["degraded"] = not all(
        provenance[name]["available"] for name in ("atmospheric", "soil_moisture", "vegetation_water_content", "previous_day_aod")
    )
    return atmospheric, surface, provenance, raw_data


def save_payload_for_swagger(lat, lon, date, filename="swagger_payload.json"):
    """Export the canonical input payload used by the prediction service."""
    print(f"Fetching data for {lat:.3f}N, {lon:.3f}E on {date.strftime('%Y-%m-%d')}...")
    atmospheric, surface, _, _ = asyncio.run(
        build_prediction_inputs(lat, lon, date)
    )
    payload = {"atmospheric": atmospheric, "surface": surface}

    with open(filename, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Saved: {filename}")
    return payload


if __name__ == "__main__":
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    save_payload_for_swagger(13.529, 2.665, tomorrow,
                             filename="swagger_banizoumbou_forecast.json")
    save_payload_for_swagger(12.364, -1.476, tomorrow,
                             filename="swagger_ouagadougou_forecast.json")

    print("\nDone.")
