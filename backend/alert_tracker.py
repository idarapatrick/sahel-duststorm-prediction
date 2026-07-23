"""Create auditable revisions of centrally monitored dust predictions.

Each run uses the deployed model unchanged, preserves the new probability even
when it decreases, and reports the actual mixture of forecasts, analyses,
delayed observations, fallbacks, and missing values.
"""

import json
import os
import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from data_pipeline import (
    build_prediction_inputs,
    get_location_name,
)
from history_store import (
    load_progressive_state,
    purge_expired,
    query_active_progressive_states,
    save_progressive_state,
)
from evidence_store import (
    evidence_fingerprint,
    evidence_summary,
    latest_fingerprint,
    records_from_prediction,
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
_MODEL_CLIENT: httpx.AsyncClient | None = None


class EvidenceUnchanged(RuntimeError):
    """Signal that a scheduled run has no new model input information."""

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


def _tracking_key(lat: float, lon: float, target_time: str) -> str:
    return f"{lat:.3f}_{lon:.3f}_{target_time}"


def _current_conditions(raw_data: dict, now: datetime, surface: list) -> dict:
    """Extract measured/forecast environmental values nearest to now."""
    hourly = raw_data["hourly"]
    target = now.replace(minute=0, second=0, microsecond=0, tzinfo=None)
    index = min(
        range(len(hourly["time"])),
        key=lambda i: abs(datetime.strptime(hourly["time"][i], "%Y-%m-%dT%H:%M") - target),
    )
    wind_speed = float(hourly["wind_speed_10m"][index] or 0)
    wind_direction = float(hourly["wind_direction_10m"][index] or 0)
    temperature = float(hourly["temperature_2m"][index] or 0)
    pressure = float(hourly["surface_pressure"][index] or 0)
    precipitation = float(hourly["precipitation"][index] or 0)
    dewpoint = float(hourly["dewpoint_2m"][index] or 0)
    return {
        "observed_at": hourly["time"][index] + ":00Z",
        "wind_speed_ms": round(wind_speed, 1),
        "wind_speed_kmh": round(wind_speed * 3.6, 1),
        "wind_direction_deg": round(wind_direction),
        "temperature_c": round(temperature, 1),
        "surface_pressure_hpa": round(pressure, 1),
        "precipitation_mm": round(precipitation, 2),
        "dewpoint_c": round(dewpoint, 1),
        "soil_moisture": round(float(surface[0]), 4),
        "vegetation_water_content": round(float(surface[1]), 4),
        "aod": round(float(surface[2]), 4),
    }


def _explain_prediction(probability: float, conditions: dict) -> str:
    """Plain-language signal summary; this is not model attribution."""
    signals = []
    if conditions["wind_speed_ms"] >= 8:
        signals.append(f"strong {conditions['wind_speed_kmh']:.0f} km/h winds can lift and transport loose dust")
    elif conditions["wind_speed_ms"] >= 5:
        signals.append(f"moderate {conditions['wind_speed_kmh']:.0f} km/h winds support dust movement")
    else:
        signals.append(f"winds are relatively light at {conditions['wind_speed_kmh']:.0f} km/h")
    if conditions["soil_moisture"] < 0.1:
        signals.append("dry surface soil is easier to disturb")
    else:
        signals.append("available soil moisture may reduce dust emission")
    if conditions["aod"] >= 0.3:
        signals.append(f"AOD of {conditions['aod']:.2f} indicates elevated atmospheric dust")
    elif conditions["aod"] > 0:
        signals.append(f"AOD is {conditions['aod']:.2f}")
    else:
        signals.append("recent satellite AOD is unavailable")
    conclusion = "Together, these signals support a higher dust-event likelihood." if probability >= 0.5 else "Together, these signals currently support a lower dust-event likelihood."
    return "; ".join(signals).capitalize() + ". " + conclusion


async def run_prediction(atmospheric: list, surface: list) -> dict:
    """Call the deployed model through one reusable worker HTTP connection pool."""
    global _MODEL_CLIENT
    if _MODEL_CLIENT is None or _MODEL_CLIENT.is_closed:
        _MODEL_CLIENT = httpx.AsyncClient(
            timeout=30,
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )
    response = await _MODEL_CLIENT.post(
        HF_SPACE_URL,
        json={"atmospheric": atmospheric, "surface": surface},
    )
    if response.status_code != 200:
        raise RuntimeError(f"Model API returned {response.status_code}")
    return response.json()


async def progressive_predict(lat: float, lon: float, target_date: datetime) -> dict:
    """Run one revision for a target day using the latest eligible evidence."""
    loop = asyncio.get_event_loop()
    now = datetime.now(timezone.utc)
    target_key = _tracking_key(lat, lon, target_date.strftime("%Y-%m-%d"))

    location_name = await loop.run_in_executor(None, get_location_name, lat, lon)

    target_time = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    if target_time.tzinfo is None:
        target_time = target_time.replace(tzinfo=timezone.utc)
    atmospheric, surface, provenance, raw_data = await build_prediction_inputs(
        lat, lon, target_date, loop
    )
    sm, vwc, prev_aod = surface[:3]
    smap_observed_at = provenance["soil_moisture"]["observed_at"]
    aod_observed_at = provenance["previous_day_aod"]["observed_at"]
    aod_source = provenance["previous_day_aod"]["source"]
    soil_source = provenance["soil_moisture"]["source"]
    conditions = _current_conditions(raw_data, now, surface)

    provisional_result = {
        "surface_data": {
            "soil_moisture": round(sm, 4),
            "vegetation_water_content": round(vwc, 4),
            "prev_day_aod": round(prev_aod, 4),
        },
        "evidence_provenance": provenance,
    }
    evidence_records = records_from_prediction(provisional_result)
    fingerprint = evidence_fingerprint(evidence_records)
    if latest_fingerprint(lat, lon, target_date.strftime("%Y-%m-%d")) == fingerprint:
        raise EvidenceUnchanged(
            "The latest provider responses contain the same prediction evidence"
        )
    composition = evidence_summary(evidence_records)
    model_result = await run_prediction(atmospheric, surface)
    current_prob = model_result["probability"]
    current_alert = get_alert_level(current_prob)
    update_record = {
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "probability": current_prob,
        "alert_level": current_alert["level"],
        "observed_fraction": composition["observed_fraction"],
        "forecast_fraction": composition["forecast_fraction"],
        "input_completeness": composition["input_completeness"],
        "soil_moisture": round(sm, 4),
        "vegetation_water_content": round(vwc, 4),
        "prev_day_aod": round(prev_aod, 4),
    }

    history = load_progressive_state(target_key) or {
        "lat": lat,
        "lon": lon,
        "location_name": location_name,
        "target_date": target_date.strftime("%Y-%m-%d"),
        "target_time": target_time.strftime("%Y-%m-%dT%H:00Z"),
        "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updates": [],
        "current_alert": current_alert,
        "trend": "new",
    }
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
    save_progressive_state(target_key, history)

    hours_until_event = max(0, (target_time - now).total_seconds() / 3600)

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
            "Conditions should be watched for changes."
        )
    elif current_alert["level"] == "warning":
        alert_message = (
            f"WARNING: Dust event likely at {location_name} on "
            f"{target_date.strftime('%B %d')}. "
            f"Probability: {current_prob:.0%}. "
            f"Begin precautionary measures."
        )
    else:
        alert_message = (
            f"ALERT: Dust event expected at {location_name} on "
            f"{target_date.strftime('%B %d')}. "
            f"Probability: {current_prob:.0%}. "
            f"Seek shelter. Cover water sources. Keep children indoors."
        )

    if trend == "decreasing" and len(previous_updates) > 0:
        prev_level = previous_updates[-1]["alert_level"]
        if prev_level in ["warning", "alert"] and current_alert["level"] in ["clear", "watch"]:
            alert_message = (
                f"UPDATE: Previous {prev_level.upper()} for {location_name} "
                f"has been downgraded to {current_alert['level'].upper()}. "
                f"New environmental information indicates reduced dust risk. "
                f"Probability dropped from {previous_updates[-1]['probability']:.0%} "
                f"to {current_prob:.0%}."
            )

    response = {
        "lat": lat,
        "lon": lon,
        "location_name": location_name,
        "target_date": target_date.strftime("%Y-%m-%d"),
        "target_time": target_time.strftime("%Y-%m-%dT%H:00Z"),
        "prediction_time": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hours_until_event": round(hours_until_event, 1),
        "probability": current_prob,
        "alert_level": current_alert["level"],
        "alert_label": current_alert["label"],
        "dust_event": model_result["dust_event"],
        "risk_level": model_result["risk_level"],
        "data_composition": {
            **composition,
            "description": (
                "This revision uses forecast, analysis, and available "
                "environmental readings as identified in its evidence record."
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
        "evidence_provenance": provenance,
        "evidence_fingerprint": fingerprint,
        "current_conditions": conditions,
        "explanation": _explain_prediction(current_prob, conditions),
        "explanation_method": "rule-based summary of model inputs; not causal feature attribution",
        "input_quality": {
            "degraded": smap_observed_at is None or aod_observed_at is None,
            "atmospheric": {"source": "open-meteo", "available": True},
            "soil_moisture": {"source": soil_source, "observed_at": smap_observed_at, "available": True},
            "vegetation_water_content": {"source": "smap" if smap_observed_at else None, "observed_at": smap_observed_at, "available": smap_observed_at is not None},
            "previous_day_aod": {
                "source": aod_source,
                "observed_at": aod_observed_at,
                "available": aod_observed_at is not None,
                "kind": provenance["previous_day_aod"].get("kind"),
            },
            "warning": "One or more expected satellite observations were unavailable; fallback model values were used." if smap_observed_at is None or aod_observed_at is None else None,
        },
        "history": history["updates"],
        "alert_message": alert_message,
    }

    return response


def get_all_tracked() -> list:
    return query_active_progressive_states()


def clear_expired():
    """Remove expired durable state using the configured retention policy."""
    purge_expired()
