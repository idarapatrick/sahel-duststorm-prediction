import os
import asyncio
from datetime import date, datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv
from fastapi import Cookie, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load deployment/local configuration before importing storage modules, which
# intentionally read DATABASE_URL once at process start.
load_dotenv()

from data_pipeline import fetch_current_conditions, fetch_features, fetch_features_for_date, fetch_forecast, get_location_name
from alert_tracker import progressive_predict, get_all_tracked, clear_expired
from history_store import RETENTION_DAYS, database_status, query_recent_snapshots, query_snapshots, save_snapshot
from auth_store import AuthError, request_otp as create_otp_challenge, revoke_session, session_user, verify_otp as consume_otp

HF_SPACE_URL = os.getenv(
    "HF_SPACE_URL", "https://mavencodes-saheldust-api.hf.space/predict"
)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
# Intentionally unset in deployment until final model evaluation and ONNX export.
MULTI_HORIZON_MODEL_URL = os.getenv("MULTI_HORIZON_MODEL_URL")

app = FastAPI(title="SahelWatch API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


class LocationPrediction(BaseModel):
    lat: float
    lon: float
    location_name: str
    probability: float
    risk_level: str
    dust_event: bool
    prediction_date: str
    data_source: str
    current_conditions: dict
    surface_data: dict


class ForecastDay(BaseModel):
    date: str
    probability: float
    risk_level: str
    dust_event: bool


class MultiDayForecast(BaseModel):
    lat: float
    lon: float
    location_name: str
    generated_at: str
    days: list[ForecastDay]


class HistoricalSnapshot(BaseModel):
    id: str
    lat: float
    lon: float
    location_name: str
    target_date: str
    recorded_at: str
    probability: float
    alert_level: str
    dust_event: bool
    data_source: str
    model_version: str | None = None


class DailyHorizonPrediction(BaseModel):
    horizon: str
    target_date: str
    approximate_lead_time: str
    probability: float
    alert_level: str
    dust_event: bool


class DailyHorizonResponse(BaseModel):
    lat: float
    lon: float
    location_name: str
    reference_date: str
    generated_at: str
    model_version: str | None = None
    current_conditions: dict
    surface_data: dict
    horizons: list[DailyHorizonPrediction]


class CurrentConditionsResponse(BaseModel):
    lat: float
    lon: float
    location_name: str
    current_conditions: dict


class OtpRequest(BaseModel):
    phone: str
    purpose: str
    device_id: str | None = None


class PreferredLocation(BaseModel):
    name: str
    lat: float
    lon: float


class OtpVerification(BaseModel):
    challenge_id: str
    code: str
    preferred_location: PreferredLocation | None = None


def _request_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",", 1)[0].strip() if forwarded else (request.client.host if request.client else None)


def _auth_error(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def probability_to_alert(probability: float) -> str:
    if probability >= 0.7:
        return "alert"
    if probability >= 0.5:
        return "warning"
    if probability >= 0.3:
        return "watch"
    return "clear"


def validate_sahel_point(lat: float, lon: float) -> None:
    if not (10 <= lat <= 25):
        raise HTTPException(400, "Latitude must be between 10 and 25 (validated Sahel region)")
    if not (-18 <= lon <= 25):
        raise HTTPException(400, "Longitude must be between -18 and 25 (validated Sahel region)")


@app.get("/")
async def root():
    return {
        "service": "SahelWatch API",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


@app.get("/api/v1/health")
async def health():
    storage = database_status()
    if not storage["available"]:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "database": storage})
    return {"status": "ok", "database": storage}


@app.post("/api/v1/auth/request-otp")
async def auth_request_otp(payload: OtpRequest, request: Request):
    if payload.purpose not in {"signup", "login"}:
        raise HTTPException(400, "purpose must be signup or login")
    try:
        return await create_otp_challenge(payload.phone, payload.purpose, payload.device_id, _request_ip(request))
    except AuthError as exc:
        raise _auth_error(exc) from exc


@app.post("/api/v1/auth/verify-otp")
async def auth_verify_otp(payload: OtpVerification, request: Request, response: Response):
    if not (payload.code.isdigit() and len(payload.code) == 6):
        raise HTTPException(400, "Enter the six-digit verification code")
    location = payload.preferred_location.model_dump() if payload.preferred_location else None
    if location:
        validate_sahel_point(location["lat"], location["lon"])
    try:
        result = consume_otp(payload.challenge_id, payload.code, location, _request_ip(request))
    except AuthError as exc:
        raise _auth_error(exc) from exc
    response.set_cookie(
        "sahelwatch_session", result["token"], httponly=True, secure=True,
        samesite="none", max_age=30 * 86400, path="/",
    )
    return {"authenticated": True, "phone_uid": result["phone_uid"], "expires_at": result["expires_at"].isoformat()}


@app.get("/api/v1/auth/me")
async def auth_me(sahelwatch_session: str | None = Cookie(default=None)):
    user = session_user(sahelwatch_session)
    return {"authenticated": bool(user), "user": user}


@app.post("/api/v1/auth/logout")
async def auth_logout(response: Response, sahelwatch_session: str | None = Cookie(default=None)):
    revoke_session(sahelwatch_session)
    response.delete_cookie("sahelwatch_session", path="/", secure=True, samesite="none")
    return {"authenticated": False}


@app.get("/api/v1/predict/location", response_model=LocationPrediction)
async def predict_location(lat: float, lon: float):
    validate_sahel_point(lat, lon)

    try:
        (atmospheric, surface, prediction_date), current_conditions = await asyncio.gather(
            fetch_features(lat, lon), fetch_current_conditions(lat, lon)
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    location_name = get_location_name(lat, lon)

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            HF_SPACE_URL,
            json={"atmospheric": atmospheric, "surface": surface},
        )

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Model API request failed")

    result = response.json()
    prediction = LocationPrediction(
        lat=lat,
        lon=lon,
        location_name=location_name,
        probability=result["probability"],
        risk_level=result["risk_level"],
        dust_event=result["dust_event"],
        prediction_date=prediction_date,
        data_source="open-meteo+gee",
        current_conditions=current_conditions,
        surface_data={
            "soil_moisture": round(float(surface[0]), 4),
            "vegetation_water_content": round(float(surface[1]), 4),
            "prev_day_aod": round(float(surface[2]), 4),
        },
    )
    save_snapshot({
        "lat": lat, "lon": lon, "location_name": location_name,
        "target_date": prediction_date, "probability": result["probability"],
        "alert_level": probability_to_alert(result["probability"]),
        "dust_event": result["dust_event"], "data_source": "open-meteo+gee",
        "metadata": {"risk_level": result["risk_level"], "endpoint": "predict/location"},
    })
    return prediction


@app.get("/api/v1/conditions/current", response_model=CurrentConditionsResponse)
async def current_conditions(lat: float, lon: float):
    """Return dashboard weather values without running ML inference."""
    validate_sahel_point(lat, lon)
    try:
        conditions = await fetch_current_conditions(lat, lon)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return CurrentConditionsResponse(
        lat=lat,
        lon=lon,
        location_name=get_location_name(lat, lon),
        current_conditions=conditions,
    )


@app.get("/api/v1/forecast", response_model=MultiDayForecast)
async def forecast(lat: float, lon: float, days: int = 3):
    validate_sahel_point(lat, lon)
    if days < 1 or days > 7:
        raise HTTPException(400, "Days must be between 1 and 7")

    location_name = get_location_name(lat, lon)

    try:
        forecast_data = await fetch_forecast(lat, lon, days_ahead=days)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    forecast_days = []
    for day_data in forecast_data:
        if "error" in day_data:
            forecast_days.append(ForecastDay(
                date=day_data["date"],
                probability=0.0,
                risk_level="unavailable",
                dust_event=False,
            ))
            continue

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                HF_SPACE_URL,
                json={
                    "atmospheric": day_data["atmospheric"],
                    "surface": day_data["surface"],
                },
            )

        if response.status_code == 200:
            result = response.json()
            forecast_days.append(ForecastDay(
                date=day_data["date"],
                probability=result["probability"],
                risk_level=result["risk_level"],
                dust_event=result["dust_event"],
            ))
        else:
            forecast_days.append(ForecastDay(
                date=day_data["date"],
                probability=0.0,
                risk_level="error",
                dust_event=False,
            ))

    return MultiDayForecast(
        lat=lat,
        lon=lon,
        location_name=location_name,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        days=forecast_days,
    )


@app.get("/api/v1/predict/progressive")
async def predict_progressive(lat: float, lon: float, target_date: str = None):
    """
    Progressive prediction. Each call uses the latest mix of real
    observations and forecast data. Call repeatedly as the target
    date approaches to get progressively more confident predictions.
    """
    validate_sahel_point(lat, lon)

    if target_date is None:
        target = datetime.now(timezone.utc) + timedelta(days=1)
    else:
        try:
            target = datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "target_date must be YYYY-MM-DD format")

    try:
        result = await progressive_predict(lat, lon, target)
        save_snapshot({
            "lat": lat, "lon": lon, "location_name": result["location_name"],
            "target_date": result["target_date"], "recorded_at": result["prediction_time"],
            "probability": result["probability"], "alert_level": result["alert_level"],
            "dust_event": result["dust_event"], "data_source": "progressive-open-meteo+gee",
            "metadata": {"confidence": result["data_composition"]["confidence_pct"], "trend": result["trend"]},
        })
        return result
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/alerts/active")
async def active_alerts():
    """Returns all currently tracked predictions with their alert levels."""
    clear_expired()
    tracked = get_all_tracked()
    active = [t for t in tracked if t["current_alert"]["level"] != "clear"]
    return {
        "total_tracked": len(tracked),
        "active_alerts": len(active),
        "predictions": tracked,
    }


# PENDING: Re-enable this route decorator only after final model evaluation and
# ONNX export have completed and MULTI_HORIZON_MODEL_URL points to the validated
# inference service. The implementation is deliberately retained below.
# @app.get(
#     "/api/v1/predict/daily-horizons",
#     response_model=DailyHorizonResponse,
# )
async def predict_daily_horizons(lat: float, lon: float):
    """Run one inference producing day+0/day+1/day+2 daily probabilities."""
    validate_sahel_point(lat, lon)
    if not MULTI_HORIZON_MODEL_URL:
        raise HTTPException(
            status_code=501,
            detail=(
                "The day+0/day+1/day+2 model is not deployed. Set "
                "MULTI_HORIZON_MODEL_URL after training and ONNX validation."
            ),
        )
    try:
        (atmospheric, surface, reference_date), conditions = await asyncio.gather(
            fetch_features(lat, lon), fetch_current_conditions(lat, lon)
        )
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                MULTI_HORIZON_MODEL_URL,
                json={"atmospheric": atmospheric, "surface": surface},
            )
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    if response.status_code != 200:
        raise HTTPException(502, "Multi-horizon model API request failed")

    payload = response.json()
    raw_horizons = payload.get("horizons")
    required = ("day_0", "day_1", "day_2")
    if not isinstance(raw_horizons, dict) or any(key not in raw_horizons for key in required):
        raise HTTPException(502, "Model response must contain horizons.day_0/day_1/day_2")

    reference = datetime.strptime(reference_date, "%Y-%m-%d").date()
    lead_times = {
        "day_0": "approximately 12-24 hours",
        "day_1": "approximately 24-48 hours",
        "day_2": "approximately 48-72 hours",
    }
    location_name = get_location_name(lat, lon)
    predictions = []
    for offset, key in enumerate(required):
        item = raw_horizons[key]
        probability = float(item["probability"])
        target_date = (reference + timedelta(days=offset)).isoformat()
        prediction = DailyHorizonPrediction(
            horizon=key.replace("_", "+"),
            target_date=target_date,
            approximate_lead_time=lead_times[key],
            probability=probability,
            alert_level=probability_to_alert(probability),
            dust_event=bool(item.get("dust_event", probability >= 0.5)),
        )
        predictions.append(prediction)
        save_snapshot({
            "lat": lat, "lon": lon, "location_name": location_name,
            "target_date": target_date, "probability": probability,
            "alert_level": prediction.alert_level,
            "dust_event": prediction.dust_event,
            "data_source": "daily-multi-horizon-model",
            "model_version": payload.get("model_version"),
            "metadata": {"horizon": prediction.horizon, "reference_date": reference_date},
        })

    return DailyHorizonResponse(
        lat=lat, lon=lon, location_name=location_name,
        reference_date=reference_date,
        generated_at=datetime.now(timezone.utc).isoformat(),
        model_version=payload.get("model_version"),
        current_conditions=conditions,
        surface_data={
            "soil_moisture": round(float(surface[0]), 4),
            "vegetation_water_content": round(float(surface[1]), 4),
            "prev_day_aod": round(float(surface[2]), 4),
        },
        horizons=predictions,
    )


@app.get("/api/v1/predict/daily-horizons", status_code=501)
async def daily_horizons_pending():
    """Stable fallback while the retained multi-horizon implementation is disabled."""
    raise HTTPException(
        status_code=501,
        detail=(
            "Daily multi-horizon prediction is coming soon. It remains disabled "
            "pending final model evaluation and ONNX export."
        ),
    )


@app.get("/api/v1/history")
async def prediction_history(lat: float, lon: float, date: str):
    """Return snapshots recorded for a point and target date within the last 90 days."""
    validate_sahel_point(lat, lon)
    try:
        requested_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(400, "date must be YYYY-MM-DD format") from exc

    today = datetime.now(timezone.utc).date()
    oldest = today - timedelta(days=RETENTION_DAYS - 1)
    if requested_date < oldest or requested_date > today:
        raise HTTPException(400, f"date must be between {oldest} and {today}")

    try:
        snapshots = query_snapshots(lat, lon, requested_date)
    except Exception as exc:
        raise HTTPException(503, "Historical prediction storage is unavailable") from exc
    return {
        "lat": lat,
        "lon": lon,
        "date": requested_date.isoformat(),
        "retention_days": RETENTION_DAYS,
        "snapshots": [HistoricalSnapshot(**item) for item in snapshots],
    }


@app.get("/api/v1/history/recent")
async def recent_prediction_history(lat: float, lon: float, limit: int = 10):
    validate_sahel_point(lat, lon)
    if limit < 1 or limit > 50:
        raise HTTPException(400, "limit must be between 1 and 50")
    snapshots = query_recent_snapshots(lat, lon, limit)
    return {"lat": lat, "lon": lon, "retention_days": RETENTION_DAYS, "snapshots": [HistoricalSnapshot(**item) for item in snapshots]}
