import os
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from data_pipeline import fetch_features, fetch_features_for_date, fetch_forecast, get_location_name
from alert_tracker import progressive_predict, get_all_tracked, clear_expired

load_dotenv()

HF_SPACE_URL = os.getenv(
    "HF_SPACE_URL", "https://mavencodes-saheldust-api.hf.space/predict"
)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app = FastAPI(title="SahelDust API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/")
async def root():
    return {
        "service": "SahelDust API",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}


@app.get("/api/v1/predict/location", response_model=LocationPrediction)
async def predict_location(lat: float, lon: float):
    if not (10 <= lat <= 25):
        raise HTTPException(400, "Latitude must be between 10 and 25 (Sahel region)")
    if not (-18 <= lon <= 25):
        raise HTTPException(400, "Longitude must be between -18 and 25 (Sahel region)")

    try:
        atmospheric, surface, prediction_date = await fetch_features(lat, lon)
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
    return LocationPrediction(
        lat=lat,
        lon=lon,
        location_name=location_name,
        probability=result["probability"],
        risk_level=result["risk_level"],
        dust_event=result["dust_event"],
        prediction_date=prediction_date,
        data_source="open-meteo+gee",
    )


@app.get("/api/v1/forecast", response_model=MultiDayForecast)
async def forecast(lat: float, lon: float, days: int = 3):
    if not (10 <= lat <= 25):
        raise HTTPException(400, "Latitude must be between 10 and 25")
    if not (-18 <= lon <= 25):
        raise HTTPException(400, "Longitude must be between -18 and 25")
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
    if not (10 <= lat <= 25):
        raise HTTPException(400, "Latitude must be between 10 and 25")
    if not (-18 <= lon <= 25):
        raise HTTPException(400, "Longitude must be between -18 and 25")

    if target_date is None:
        target = datetime.now(timezone.utc) + timedelta(days=1)
    else:
        try:
            target = datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "target_date must be YYYY-MM-DD format")

    try:
        result = await progressive_predict(lat, lon, target)
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