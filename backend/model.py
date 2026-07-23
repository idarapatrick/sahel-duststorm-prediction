"""Validated request and response contracts for the SahelWatch API.

The deployed neural network is served by the configured Hugging Face model
service. This module defines the backend-facing data models and deliberately
does not claim to load model weights locally. Research model definitions and
experiments are retained under ``ml/`` and ``notebooks/``.
"""

from pydantic import BaseModel, Field


class LocationPrediction(BaseModel):
    """Single daily dust-risk response for one supported coordinate."""
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
    """One calendar-day result returned by a validated horizon model."""
    date: str
    probability: float = Field(ge=0.0, le=1.0)
    risk_level: str
    dust_event: bool


class MultiDayForecast(BaseModel):
    """Collection of daily results sharing one issue time and location."""
    lat: float
    lon: float
    location_name: str
    generated_at: str
    days: list[ForecastDay]


class HistoricalSnapshot(BaseModel):
    """Immutable prediction revision exposed through the history API."""
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
    """One disabled multi-horizon head retained for future deployment."""
    horizon: str
    target_date: str
    approximate_lead_time: str
    probability: float = Field(ge=0.0, le=1.0)
    alert_level: str
    dust_event: bool


class DailyHorizonResponse(BaseModel):
    """Response contract for the pending three-head daily model."""
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
    """Latest provider conditions displayed beside a prediction."""
    lat: float
    lon: float
    location_name: str
    current_conditions: dict


class OtpRequest(BaseModel):
    """Legacy phone-verification request retained during Firebase migration."""
    phone: str
    purpose: str
    device_id: str | None = None


class PreferredLocation(BaseModel):
    """User-selected forecast location stored with a phone account."""
    name: str
    lat: float
    lon: float


class OtpVerification(BaseModel):
    """Legacy OTP challenge answer and optional initial location."""
    challenge_id: str
    code: str
    preferred_location: PreferredLocation | None = None


class AccountDeletionRequest(BaseModel):
    """Request to begin verified account deletion."""
    device_id: str | None = None


class AccountDeletionConfirmation(BaseModel):
    """Verified legacy OTP confirmation for account deletion."""
    challenge_id: str
    code: str


class FirebaseSessionRequest(BaseModel):
    """Firebase identity token exchanged for a SahelWatch session."""
    id_token: str
    purpose: str
    device_id: str | None = None
    preferred_location: PreferredLocation | None = None


class FirebaseAccountDeletion(BaseModel):
    """Fresh Firebase identity proof used to schedule account deletion."""
    id_token: str


class SubscriptionRequest(BaseModel):
    """SMS alert preference for one centrally monitored forecast cell."""
    lat: float
    lon: float
    location_name: str
    threshold: str = "warning"
