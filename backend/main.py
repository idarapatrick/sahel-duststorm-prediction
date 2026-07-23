import os
import asyncio
import time
from datetime import date, datetime, timedelta, timezone

import httpx
from fastapi import Cookie, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Load deployment/local configuration before importing storage modules, which
# intentionally read DATABASE_URL once at process start.
load_dotenv()

from data_pipeline import GEE_AVAILABLE, fetch_current_conditions, fetch_features, fetch_features_for_date, get_location_name
from alert_tracker import get_all_tracked, clear_expired
from history_store import RETENTION_DAYS, database_status, query_latest_environmental_evidence, query_recent_snapshots, query_snapshots, save_snapshot
from auth_store import AuthError, confirm_account_deletion, request_account_deletion_otp, request_otp as create_otp_challenge, require_session, revoke_session, session_user, verify_otp as consume_otp
from alert_store import delete_subscription, list_subscriptions, notification_feed, operational_status, upsert_subscription
from rate_limit import RateLimitExceeded, enforce_rate_limit
from observability import configure_logging, log_event
from coverage_store import coverage_status, list_covered_places, nearest_covered_place
from firebase_auth import create_firebase_session, delete_firebase_account, firebase_configured
from sms_provider import alert_provider_name, twilio_configured
from model import (
    AccountDeletionConfirmation,
    AccountDeletionRequest,
    CurrentConditionsResponse,
    DailyHorizonPrediction,
    DailyHorizonResponse,
    FirebaseAccountDeletion,
    FirebaseSessionRequest,
    HistoricalSnapshot,
    OtpRequest,
    OtpVerification,
    SubscriptionRequest,
)

HF_SPACE_URL = os.getenv(
    "HF_SPACE_URL", "https://mavencodes-saheldust-api.hf.space/predict"
)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
# Intentionally unset in deployment until final model evaluation and ONNX export.
MULTI_HORIZON_MODEL_URL = os.getenv("MULTI_HORIZON_MODEL_URL")

app = FastAPI(title="SahelWatch API")
logger = configure_logging()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.middleware("http")
async def request_metrics(request: Request, call_next):
    started = time.monotonic()
    try:
        response = await call_next(request)
        log_event(logger, "http_request", method=request.method, path=request.url.path,
                  status=response.status_code, duration_ms=round((time.monotonic()-started)*1000))
        return response
    except Exception as exc:
        log_event(logger, "http_error", method=request.method, path=request.url.path,
                  error=type(exc).__name__, duration_ms=round((time.monotonic()-started)*1000))
        raise


@app.exception_handler(Exception)
async def unhandled_api_error(request: Request, exc: Exception):
    """Return a safe JSON error so CORS middleware can preserve browser access."""
    log_event(logger, "unhandled_api_error", method=request.method, path=request.url.path,
              error=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"detail": "The SahelWatch backend encountered an internal error"},
    )


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
        raise HTTPException(400, "Latitude must be between 10 and 25 (configured Sahel region)")
    if not (-18 <= lon <= 25):
        raise HTTPException(400, "Longitude must be between -18 and 25 (configured Sahel region)")


@app.get("/")
async def root():
    return {
        "service": "SahelWatch API",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


@app.get("/api/v1/coverage/places")
async def coverage_places(q: str | None = None, country: str | None = None, limit: int = 250):
    """List database-backed communities mapped to centrally monitored cells."""
    if q is not None and len(q.strip()) > 80:
        raise HTTPException(400, "Search text is too long")
    country_code = country.strip().upper() if country else None
    if country_code and (len(country_code) != 2 or not country_code.isalpha()):
        raise HTTPException(400, "country must be a two-letter country code")
    places = list_covered_places(q.strip() if q and q.strip() else None, country_code, limit)
    return {"places": places, "count": len(places)}


@app.get("/api/v1/coverage/nearest")
async def coverage_nearest(lat: float, lon: float):
    """Map device coordinates to the nearest monitored community and grid cell."""
    validate_sahel_point(lat, lon)
    place = nearest_covered_place(lat, lon)
    if not place:
        raise HTTPException(503, "No forecast locations are currently available")
    return {"place": place}


@app.get("/api/v1/health")
async def health():
    storage = database_status()
    if not storage["available"]:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "database": storage})
    try:
        operations = operational_status()
    except Exception as exc:
        operations = {"available": False, "error": type(exc).__name__}
    try:
        operations["coverage"] = coverage_status()
    except Exception as exc:
        operations["coverage"] = {"available": False, "error": type(exc).__name__}
    return {
        "status": "ok", "database": storage,
        "earth_engine": {"available": GEE_AVAILABLE},
        "model": {"configured": bool(HF_SPACE_URL)},
        "authentication": {
            "provider": "firebase" if firebase_configured() else "legacy_otp",
            "firebase_configured": firebase_configured(),
        },
        "sms": {
            "provider": alert_provider_name(),
            "configured": twilio_configured() if alert_provider_name() == "twilio" else bool(os.getenv("AFRICASTALKING_USERNAME") and os.getenv("AFRICASTALKING_API_KEY")),
            "sender_configured": bool(os.getenv("TWILIO_MESSAGING_SERVICE_SID") or os.getenv("TWILIO_FROM_NUMBER")) if alert_provider_name() == "twilio" else bool(os.getenv("AFRICASTALKING_SENDER_ID", "").strip()),
        },
        "operations": operations,
    }


@app.post("/api/v1/auth/firebase/session")
async def auth_firebase_session(payload: FirebaseSessionRequest, request: Request, response: Response):
    location = payload.preferred_location.model_dump() if payload.preferred_location else None
    if location:
        validate_sahel_point(location["lat"], location["lon"])
    try:
        result = create_firebase_session(
            payload.id_token, payload.purpose, location, payload.device_id, _request_ip(request)
        )
    except AuthError as exc:
        raise _auth_error(exc) from exc
    response.set_cookie(
        "sahelwatch_session", result["token"], httponly=True, secure=True,
        samesite="none", max_age=30 * 86400, path="/",
    )
    return {
        "authenticated": True, "phone_uid": result["phone_uid"],
        "firebase_uid": result["firebase_uid"], "expires_at": result["expires_at"].isoformat(),
    }


@app.post("/api/v1/auth/firebase/account/delete")
async def auth_delete_firebase_account(
    payload: FirebaseAccountDeletion,
    response: Response,
    sahelwatch_session: str | None = Cookie(default=None),
):
    try:
        user = require_session(sahelwatch_session)
        if user.get("auth_provider") != "firebase":
            raise AuthError(409, "This account still uses the previous verification service")
        delete_firebase_account(user, payload.id_token)
    except AuthError as exc:
        raise _auth_error(exc) from exc
    response.delete_cookie("sahelwatch_session", path="/", secure=True, samesite="none")
    return {"deleted": True}


@app.post("/api/v1/auth/request-otp")
async def auth_request_otp(payload: OtpRequest, request: Request):
    if payload.purpose not in {"signup", "login"}:
        raise HTTPException(400, "purpose must be signup or login")
    try:
        enforce_rate_limit(_request_ip(request) or "unknown", "otp", 5, 3600)
        return await create_otp_challenge(payload.phone, payload.purpose, payload.device_id, _request_ip(request))
    except RateLimitExceeded as exc:
        raise HTTPException(429, "Too many OTP requests", headers={"Retry-After": str(exc.retry_after)}) from exc
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


@app.post("/api/v1/auth/account/delete-otp")
async def auth_request_account_deletion(
    payload: AccountDeletionRequest,
    request: Request,
    sahelwatch_session: str | None = Cookie(default=None),
):
    try:
        enforce_rate_limit(_request_ip(request) or "unknown", "delete-otp", 5, 3600)
        return await request_account_deletion_otp(
            sahelwatch_session, payload.device_id, _request_ip(request)
        )
    except RateLimitExceeded as exc:
        raise HTTPException(429, "Too many verification requests", headers={"Retry-After": str(exc.retry_after)}) from exc
    except AuthError as exc:
        raise _auth_error(exc) from exc


@app.post("/api/v1/auth/account/confirm-delete")
async def auth_confirm_account_deletion(
    payload: AccountDeletionConfirmation,
    response: Response,
    sahelwatch_session: str | None = Cookie(default=None),
):
    if not (payload.code.isdigit() and len(payload.code) == 6):
        raise HTTPException(400, "Enter the six-digit verification code")
    try:
        confirm_account_deletion(sahelwatch_session, payload.challenge_id, payload.code)
    except AuthError as exc:
        raise _auth_error(exc) from exc
    response.delete_cookie("sahelwatch_session", path="/", secure=True, samesite="none")
    return {"deleted": True}


@app.get("/api/v1/subscriptions")
async def subscriptions(sahelwatch_session: str | None = Cookie(default=None)):
    try:
        user = require_session(sahelwatch_session)
        return {"subscriptions": list_subscriptions(user["phone_uid"])}
    except AuthError as exc:
        raise _auth_error(exc) from exc


@app.put("/api/v1/subscriptions")
async def save_subscription(payload: SubscriptionRequest, sahelwatch_session: str | None = Cookie(default=None)):
    validate_sahel_point(payload.lat, payload.lon)
    try:
        user = require_session(sahelwatch_session)
        return upsert_subscription(user["phone_uid"], payload.lat, payload.lon, payload.location_name, payload.threshold)
    except AuthError as exc:
        raise _auth_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/v1/subscriptions/{subscription_id}")
async def remove_subscription(subscription_id: str, sahelwatch_session: str | None = Cookie(default=None)):
    try:
        user = require_session(sahelwatch_session)
        if not delete_subscription(user["phone_uid"], subscription_id):
            raise HTTPException(404, "Subscription not found")
        return {"deleted": True}
    except AuthError as exc:
        raise _auth_error(exc) from exc


@app.get("/api/v1/notifications")
async def notifications(limit: int = 50, sahelwatch_session: str | None = Cookie(default=None)):
    if not 1 <= limit <= 100:
        raise HTTPException(400, "limit must be between 1 and 100")
    try:
        user = require_session(sahelwatch_session)
        return {"notifications": notification_feed(user["phone_uid"], limit)}
    except AuthError as exc:
        raise _auth_error(exc) from exc


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


@app.get("/api/v1/alerts/active")
async def active_alerts():
    """Returns all currently tracked predictions with their alert levels."""
    clear_expired()
    tracked = get_all_tracked()
    active = [t for t in tracked if t["current_alert"]["level"] != "clear"]
    return {
        "total_tracked": len(tracked),
        "active_alerts": len(active),
        "predictions": active,
    }


@app.get("/api/v1/predictions/latest")
async def latest_prediction(lat: float, lon: float):
    """Read the latest centrally stored result without triggering inference."""
    validate_sahel_point(lat, lon)
    central_target = (datetime.now(timezone.utc) + timedelta(days=1)).date()
    snapshots = query_snapshots(lat, lon, central_target)
    # During the short midnight rollover, keep serving the last completed
    # central result until the worker stores the first new target-day revision.
    if not snapshots:
        snapshots = query_recent_snapshots(lat, lon, 1)
    if not snapshots:
        raise HTTPException(404, "No central prediction has been recorded for this location yet")
    snapshot = snapshots[0]
    recorded_at = datetime.fromisoformat(snapshot["recorded_at"].replace("Z", "+00:00"))
    age_minutes = max(
        0, round((datetime.now(timezone.utc) - recorded_at).total_seconds() / 60, 1)
    )
    surface = snapshot.get("metadata", {}).get("surface_data")
    evidence = query_latest_environmental_evidence(lat, lon)
    if not surface and evidence:
        surface = {
            "soil_moisture": evidence.get("soil_moisture"),
            "vegetation_water_content": evidence.get("vegetation_water_content"),
            "prev_day_aod": evidence.get("aod"),
        }
    conditions = None
    if evidence:
        wind_ms = evidence.get("wind_speed_ms")
        conditions = {
            "observed_at": evidence.get("observed_at"),
            "wind_speed_ms": wind_ms,
            "wind_speed_kmh": round(wind_ms * 3.6, 1) if wind_ms is not None else None,
            "wind_direction_deg": evidence.get("wind_direction_deg"),
            "temperature_c": evidence.get("temperature_c"),
            "dewpoint_c": evidence.get("dewpoint_c"),
            "surface_pressure_hpa": evidence.get("surface_pressure_hpa"),
            "precipitation_mm": evidence.get("precipitation_mm"),
            "soil_moisture": evidence.get("soil_moisture"),
            "vegetation_water_content": evidence.get("vegetation_water_content"),
            "aod": evidence.get("aod"),
        }
    return {
        "prediction": snapshot,
        "surface_data": surface,
        "current_conditions": conditions,
        "freshness": {
            "recorded_at": snapshot["recorded_at"],
            "age_minutes": age_minutes,
            "stale": age_minutes > 90,
            "source": "central-hourly-worker",
            "target_date": snapshot["target_date"],
            "current_central_target": central_target.isoformat(),
        },
        "evidence": evidence,
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
