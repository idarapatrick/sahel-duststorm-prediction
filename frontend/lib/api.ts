import type {
  ActiveAlertsResponse,
  AlertLevel,
  ForecastResponse,
  LocationPrediction,
  MultiDayForecast,
  ProgressivePrediction,
  ProgressiveUpdate,
  RiskLevel,
  Station,
  TrackedAlert,
  WindVector,
} from "./types";

// Mock regional grid dates (Home map overlay only -- see note in getForecast).
export const FORECAST_DATES = ["2026-07-02", "2026-07-03", "2026-07-04"] as const;
export const FORECAST_DATE_LABELS = ["Today", "Tomorrow", "Day after"] as const;

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Backend enforces the same bounds and returns HTTP 400 outside them --
// validate client-side first to avoid a pointless round trip.
export const SAHEL_BOUNDS = { latMin: 10, latMax: 25, lonMin: -18, lonMax: 25 };

export function isWithinSahelBounds(lat: number, lon: number): boolean {
  return (
    lat >= SAHEL_BOUNDS.latMin &&
    lat <= SAHEL_BOUNDS.latMax &&
    lon >= SAHEL_BOUNDS.lonMin &&
    lon <= SAHEL_BOUNDS.lonMax
  );
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load ${url}: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

/**
 * A real per-cell grid would mean one 10-30s backend call per cell (hundreds
 * of them) -- infeasible live. The Home map overlay stays mock/illustrative;
 * Location and Progressive Tracking pages use the real single-point API
 * below instead.
 */
export function getForecast(date: string): Promise<ForecastResponse> {
  return getJson<ForecastResponse>(`/mock/forecast/${date}.json`);
}

export function getWind(date: string): Promise<{ date: string; vectors: WindVector[] }> {
  return getJson<{ date: string; vectors: WindVector[] }>(`/mock/forecast/wind-${date}.json`);
}

export function getStations(): Promise<Station[]> {
  return getJson<Station[]>("/mock/stations.json");
}

const RISK_LEVELS: readonly RiskLevel[] = ["low", "moderate", "high", "severe"];
const ALERT_LEVELS: readonly AlertLevel[] = ["clear", "watch", "warning", "alert"];

/** Safety net for whatever the model API returns -- validated vocab, else derived. */
function normalizeRisk(value: unknown, probability: number): RiskLevel {
  if (typeof value === "string" && RISK_LEVELS.includes(value as RiskLevel)) {
    return value as RiskLevel;
  }
  if (probability > 0.7) return "severe";
  if (probability > 0.4) return "high";
  if (probability > 0.2) return "moderate";
  return "low";
}

/** Mirrors alert_tracker.py's ALERT_LEVELS thresholds as a safety net. */
function normalizeAlertLevel(value: unknown, probability: number): AlertLevel {
  if (typeof value === "string" && ALERT_LEVELS.includes(value as AlertLevel)) {
    return value as AlertLevel;
  }
  if (probability >= 0.7) return "alert";
  if (probability >= 0.5) return "warning";
  if (probability >= 0.3) return "watch";
  return "clear";
}

async function backendGet<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

/**
 * GET /api/v1/predict/location -- single live prediction. Returns null on
 * any failure (backend down, ERA5/Open-Meteo data unavailable, out of
 * bounds) so callers can fall back to mock data.
 */
export async function getLocationPrediction(
  lat: number,
  lon: number
): Promise<LocationPrediction | null> {
  if (!isWithinSahelBounds(lat, lon)) return null;
  const data = await backendGet<Record<string, unknown>>(
    `/api/v1/predict/location?lat=${lat}&lon=${lon}`
  );
  if (!data) return null;
  const probability = data.probability as number;
  return {
    lat: data.lat as number,
    lon: data.lon as number,
    locationName: data.location_name as string,
    probability,
    risk: normalizeRisk(data.risk_level, probability),
    dustEvent: data.dust_event as boolean,
    predictionDate: data.prediction_date as string,
    dataSource: data.data_source as string,
  };
}

/** GET /api/v1/forecast -- real multi-day forecast (default 3 days). */
export async function getMultiDayForecast(
  lat: number,
  lon: number,
  days = 3
): Promise<MultiDayForecast | null> {
  if (!isWithinSahelBounds(lat, lon)) return null;
  const data = await backendGet<Record<string, unknown>>(
    `/api/v1/forecast?lat=${lat}&lon=${lon}&days=${days}`
  );
  if (!data) return null;
  const rawDays = data.days as Array<Record<string, unknown>>;
  return {
    lat: data.lat as number,
    lon: data.lon as number,
    locationName: data.location_name as string,
    generatedAt: data.generated_at as string,
    days: rawDays.map((d) => ({
      date: d.date as string,
      probability: d.probability as number,
      risk: normalizeRisk(d.risk_level, d.probability as number),
      dustEvent: d.dust_event as boolean,
    })),
  };
}

function toProgressiveUpdate(u: Record<string, unknown>): ProgressiveUpdate {
  const probability = u.probability as number;
  return {
    timestamp: u.timestamp as string,
    probability,
    alertLevel: normalizeAlertLevel(u.alert_level, probability),
    hoursRealData: u.hours_real_data as number,
    hoursForecastData: u.hours_forecast_data as number,
    confidence: u.confidence as number,
    probChange: (u.prob_change as number) ?? 0,
  };
}

/**
 * GET /api/v1/predict/progressive -- tracks a location+date across repeated
 * calls, blending real observations with forecast data as the target date
 * approaches. targetDate defaults to tomorrow (backend default) if omitted.
 */
export async function getProgressivePrediction(
  lat: number,
  lon: number,
  targetDate?: string
): Promise<ProgressivePrediction | null> {
  if (!isWithinSahelBounds(lat, lon)) return null;
  const qs = new URLSearchParams({ lat: String(lat), lon: String(lon) });
  if (targetDate) qs.set("target_date", targetDate);
  const data = await backendGet<Record<string, unknown>>(
    `/api/v1/predict/progressive?${qs.toString()}`
  );
  if (!data) return null;
  const probability = data.probability as number;
  const composition = data.data_composition as Record<string, unknown>;
  const surface = data.surface_data as Record<string, unknown>;
  return {
    lat: data.lat as number,
    lon: data.lon as number,
    locationName: data.location_name as string,
    targetDate: data.target_date as string,
    predictionTime: data.prediction_time as string,
    hoursUntilEvent: data.hours_until_event as number,
    probability,
    alertLevel: normalizeAlertLevel(data.alert_level, probability),
    alertLabel: data.alert_label as string,
    dustEvent: data.dust_event as boolean,
    risk: normalizeRisk(data.risk_level, probability),
    dataComposition: {
      hoursRealObservations: composition.hours_real_observations as number,
      hoursForecastData: composition.hours_forecast_data as number,
      confidencePct: composition.confidence_pct as number,
      description: composition.description as string,
    },
    trend: data.trend as ProgressivePrediction["trend"],
    updateCount: data.update_count as number,
    probChangeSinceLast: data.prob_change_since_last as number,
    surfaceData: {
      soilMoisture: surface.soil_moisture as number,
      vegetationWaterContent: surface.vegetation_water_content as number,
      prevDayAod: surface.prev_day_aod as number,
    },
    history: (data.history as Array<Record<string, unknown>>).map(toProgressiveUpdate),
    alertMessage: data.alert_message as string,
  };
}

/** GET /api/v1/alerts/active -- all currently tracked progressive predictions. */
export async function getActiveAlerts(): Promise<ActiveAlertsResponse | null> {
  const data = await backendGet<Record<string, unknown>>("/api/v1/alerts/active");
  if (!data) return null;
  const predictions = data.predictions as Array<Record<string, unknown>>;
  return {
    totalTracked: data.total_tracked as number,
    activeAlerts: data.active_alerts as number,
    predictions: predictions.map(
      (p): TrackedAlert => ({
        lat: p.lat as number,
        lon: p.lon as number,
        locationName: p.location_name as string,
        targetDate: p.target_date as string,
        createdAt: p.created_at as string,
        updates: (p.updates as Array<Record<string, unknown>>).map(toProgressiveUpdate),
        currentAlert: p.current_alert as TrackedAlert["currentAlert"],
        trend: p.trend as string,
      })
    ),
  };
}
