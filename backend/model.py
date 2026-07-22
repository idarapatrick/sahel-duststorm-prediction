"""Validated request and response contracts for the SahelWatch API.

The deployed neural network is served by the configured Hugging Face model
service. This module defines the backend-facing data models and deliberately
does not claim to load model weights locally. Research model definitions and
experiments are retained under ``ml/`` and ``notebooks/``.
"""

from pydantic import BaseModel, Field


class LocationPrediction(BaseModel):
    lat: float
    lon: float
    location_name: str
    probability: float = Field(ge=0.0, le=1.0)
    risk_level: str
    dust_event: bool
    prediction_date: str
    data_source: str
    current_conditions: dict
    surface_data: dict
    input_quality: dict


class ForecastDay(BaseModel):
    date: str
    probability: float = Field(ge=0.0, le=1.0)
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
    probability: float = Field(ge=0.0, le=1.0)
    alert_level: str
    dust_event: bool
    data_source: str
    model_version: str | None = None


class DailyHorizonPrediction(BaseModel):
    horizon: str
    target_date: str
    approximate_lead_time: str
    probability: float = Field(ge=0.0, le=1.0)
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


class AccountDeletionRequest(BaseModel):
    device_id: str | None = None


class AccountDeletionConfirmation(BaseModel):
    challenge_id: str
    code: str


class FirebaseSessionRequest(BaseModel):
    id_token: str
    purpose: str
    device_id: str | None = None
    preferred_location: PreferredLocation | None = None


class FirebaseAccountDeletion(BaseModel):
    id_token: str


class SubscriptionRequest(BaseModel):
    lat: float
    lon: float
    location_name: str
    threshold: str = "warning"
