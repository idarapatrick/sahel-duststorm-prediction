"""
SahelDust Progressive Alert System

Tracks predictions over time for monitored locations.
Each prediction update replaces forecast data with real observations
from Open-Meteo, progressively improving confidence.

Alert levels escalate or de-escalate based on how the probability
changes across consecutive updates.
"""

import json
import os
import asyncio
import httpx
import numpy as np
from datetime import datetime, timedelta, timezone
from data_pipeline import (
    _fetch_openmeteo_forecast,
    _extract_72h_window,
    _extract_soil_moisture,
    _fetch_smap_gee,
    _fetch_modis_aod_gee,
    get_location_name,
    GEE_AVAILABLE,
)

HF_SPACE_URL = os.getenv(
    "HF_SPACE_URL", "https://mavencodes-saheldust-api.hf.space/predict"
)

ALERT_LEVELS = {
    "clear": {"min_prob": 0.0, "max_prob": 0.3, "label": "No significant risk"},
    "watch": {"min_prob": 0.3, "max_prob": 0.5, "label": "Possible dust activity"},
    "warning": {"min_prob": 0.5, "max_prob": 0.7, "label": "Dust event likely"},
    "alert": {"min_prob": 0.7, "max_prob": 1.0, "label": "Dust event imminent"},
}

tracked_predictions = {}


def get_alert_level(probability: float) -> dict:
    for level_name, thresholds in ALERT_LEVELS.items():
        if thresholds["min_prob"] <= probability < thresholds["max_prob"]:
            return {
                "level": level_name,
                "label": thresholds["label"],
                "probability": round(probability, 4),
            }
    return {
        "level": "alert",
        "label": "Dust event imminent",
        "probability": round(probability, 4),
    }


def _tracking_key(lat: float, lon: float, target_date: str) -> str:
    return f"{lat:.3f}_{lon:.3f}_{target_date}"


async def run_prediction(atmospheric: list, surface: list) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            HF_SPACE_URL,
            json={"atmospheric": atmospheric, "surface": surface},
        )
    if response.status_code != 200:
        raise RuntimeError(f"Model API returned {response.status_code}")
    return response.json()


async def progressive_predict(lat: float, lon: float, target_date: datetime) -> dict:
    """
    Make a prediction for a target date using the latest available data.

    This is the core of the progressive system. Each time it runs:
    1. Fetches the 72-hour atmospheric window from Open-Meteo
       (Open-Meteo automatically uses real observations for past hours
        and forecast data for future hours)
    2. Fetches the latest SMAP and MODIS data from GEE
    3. Runs the prediction through the model
    4. Compares against previous predictions for the same location+date
    5. Updates the alert level based on the probability trajectory

    The atmospheric window covers T-60 to T+12 relative to target midnight.
    As time passes, more of this window transitions from forecast to
    real observations, improving prediction confidence.
    """
    loop = asyncio.get_event_loop()
    now = datetime.now(timezone.utc)
    target_key = _tracking_key(lat, lon, target_date.strftime("%Y-%m-%d"))

    location_name = await loop.run_in_executor(None, get_location_name, lat, lon)

    target_midnight = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    if target_midnight.tzinfo is None:
        target_midnight = target_midnight.replace(tzinfo=timezone.utc)
    window_start = target_midnight - timedelta(hours=60)
    window_end = target_midnight + timedelta(hours=12)

    if now < window_start:
        hours_real = 0
        hours_forecast = 72
    elif now > window_end:
        hours_real = 72
        hours_forecast = 0
    else:
        hours_real = max(0, int((now - window_start).total_seconds() / 3600))
        hours_forecast = 72 - hours_real

    raw_data = await loop.run_in_executor(
        None, _fetch_openmeteo_forecast, lat, lon, target_date
    )
    atmospheric = _extract_72h_window(raw_data, target_date)

    sm = _extract_soil_moisture(raw_data, target_date)
    vwc = 0.0
    prev_aod = 0.0

    if GEE_AVAILABLE:
        for offset in range(0, 8):
            smap_date = target_date - timedelta(days=offset)
            sm_gee, vwc_gee = await loop.run_in_executor(
                None, _fetch_smap_gee, lat, lon, smap_date
            )
            if sm_gee is not None:
                sm = sm_gee
                vwc = vwc_gee if vwc_gee is not None else 0.0
                break

        for offset in range(1, 8):
            aod_date = target_date - timedelta(days=offset)
            aod = await loop.run_in_executor(
                None, _fetch_modis_aod_gee, lat, lon, aod_date
            )
            if aod > 0:
                prev_aod = aod
                break

    month = target_date.month
    month_sin = float(np.sin(2 * np.pi * month / 12))
    month_cos = float(np.cos(2 * np.pi * month / 12))
    surface = [sm, vwc, prev_aod, lat, lon, month_sin, month_cos]

    model_result = await run_prediction(atmospheric, surface)
    current_prob = model_result["probability"]
    current_alert = get_alert_level(current_prob)

    update_record = {
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "probability": current_prob,
        "alert_level": current_alert["level"],
        "hours_real_data": hours_real,
        "hours_forecast_data": hours_forecast,
        "confidence": round(hours_real / 72 * 100, 1),
        "soil_moisture": round(sm, 4),
        "vegetation_water_content": round(vwc, 4),
        "prev_day_aod": round(prev_aod, 4),
    }

    if target_key not in tracked_predictions:
        tracked_predictions[target_key] = {
            "lat": lat,
            "lon": lon,
            "location_name": location_name,
            "target_date": target_date.strftime("%Y-%m-%d"),
            "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "updates": [],
            "current_alert": current_alert,
            "trend": "new",
        }

    history = tracked_predictions[target_key]
    previous_updates = history["updates"]

    if len(previous_updates) > 0:
        prev_prob = previous_updates[-1]["probability"]
        prob_change = current_prob - prev_prob

        if prob_change > 0.05:
            trend = "increasing"
        elif prob_change < -0.05:
            trend = "decreasing"
        else:
            trend = "stable"

        update_record["prob_change"] = round(prob_change, 4)
    else:
        trend = "new"
        update_record["prob_change"] = 0.0

    history["updates"].append(update_record)
    history["current_alert"] = current_alert
    history["trend"] = trend

    hours_until_event = max(0, (target_midnight - now).total_seconds() / 3600)

    if current_alert["level"] == "clear":
        alert_message = (
            f"No significant dust risk predicted for "
            f"{target_date.strftime('%B %d')} at {location_name}. "
            f"Conditions are within normal ranges."
        )
    elif current_alert["level"] == "watch":
        alert_message = (
            f"WATCH: Possible dust activity at {location_name} on "
            f"{target_date.strftime('%B %d')}. "
            f"Prediction based on {hours_real}/72 hours of real data "
            f"({update_record['confidence']}% confidence). Monitor for updates."
        )
    elif current_alert["level"] == "warning":
        alert_message = (
            f"WARNING: Dust event likely at {location_name} on "
            f"{target_date.strftime('%B %d')}. "
            f"Probability: {current_prob:.0%}. "
            f"Based on {hours_real}/72 hours of real observations. "
            f"Begin precautionary measures."
        )
    else:
        alert_message = (
            f"ALERT: Dust event expected at {location_name} on "
            f"{target_date.strftime('%B %d')}. "
            f"Probability: {current_prob:.0%}. "
            f"Based on {hours_real}/72 hours of confirmed observations. "
            f"Seek shelter. Cover water sources. Keep children indoors."
        )

    if trend == "decreasing" and len(previous_updates) > 0:
        prev_level = previous_updates[-1]["alert_level"]
        if prev_level in ["warning", "alert"] and current_alert["level"] in ["clear", "watch"]:
            alert_message = (
                f"UPDATE: Previous {prev_level.upper()} for {location_name} "
                f"has been downgraded to {current_alert['level'].upper()}. "
                f"Conditions have changed. Real observations show reduced dust risk. "
                f"Probability dropped from {previous_updates[-1]['probability']:.0%} "
                f"to {current_prob:.0%}."
            )

    response = {
        "lat": lat,
        "lon": lon,
        "location_name": location_name,
        "target_date": target_date.strftime("%Y-%m-%d"),
        "prediction_time": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hours_until_event": round(hours_until_event, 1),
        "probability": current_prob,
        "alert_level": current_alert["level"],
        "alert_label": current_alert["label"],
        "dust_event": model_result["dust_event"],
        "risk_level": model_result["risk_level"],
        "data_composition": {
            "hours_real_observations": hours_real,
            "hours_forecast_data": hours_forecast,
            "confidence_pct": round(hours_real / 72 * 100, 1),
            "description": (
                f"{hours_real} of 72 atmospheric hours use real observations, "
                f"{hours_forecast} use forecast data"
            ),
        },
        "trend": trend,
        "update_count": len(history["updates"]),
        "prob_change_since_last": update_record["prob_change"],
        "surface_data": {
            "soil_moisture": round(sm, 4),
            "vegetation_water_content": round(vwc, 4),
            "prev_day_aod": round(prev_aod, 4),
        },
        "history": history["updates"],
        "alert_message": alert_message,
    }

    return response


def get_all_tracked() -> list:
    return list(tracked_predictions.values())


def clear_expired():
    now = datetime.now(timezone.utc)
    expired = []
    for key, pred in tracked_predictions.items():
        target = datetime.strptime(pred["target_date"], "%Y-%m-%d")
        target = target.replace(tzinfo=timezone.utc)
        if now - target > timedelta(days=1):
            expired.append(key)
    for key in expired:
        del tracked_predictions[key]
    return len(expired)