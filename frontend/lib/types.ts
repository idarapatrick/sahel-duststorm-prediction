export type RiskLevel = "low" | "moderate" | "high" | "severe";

export type AlertLevel = "clear" | "watch" | "warning" | "alert";

export type Trend = "new" | "increasing" | "decreasing" | "stable";

// Used by components/map/ForecastMap.tsx (currently unused by any page --
// kept for the "real map tile layer under the storm-spread overlay" upgrade
// the design doc leaves as a future option).
export interface GridPrediction {
  lat: number;
  lon: number;
  probability: number;
  severity: RiskLevel;
}

// GET /api/v1/predict/location
export interface LocationPrediction {
  lat: number;
  lon: number;
  locationName: string;
  probability: number;
  risk: RiskLevel;
  dustEvent: boolean;
  predictionDate: string;
  dataSource: string;
}

// GET /api/v1/forecast
export interface ForecastDay {
  date: string;
  probability: number;
  risk: RiskLevel;
  dustEvent: boolean;
}

export interface MultiDayForecast {
  lat: number;
  lon: number;
  locationName: string;
  generatedAt: string;
  days: ForecastDay[];
}

// GET /api/v1/predict/progressive
export interface ProgressiveUpdate {
  timestamp: string;
  probability: number;
  alertLevel: AlertLevel;
  hoursRealData: number;
  hoursForecastData: number;
  confidence: number;
  probChange: number;
}

export interface ProgressivePrediction {
  lat: number;
  lon: number;
  locationName: string;
  targetDate: string;
  predictionTime: string;
  hoursUntilEvent: number;
  probability: number;
  alertLevel: AlertLevel;
  alertLabel: string;
  dustEvent: boolean;
  risk: RiskLevel;
  dataComposition: {
    hoursRealObservations: number;
    hoursForecastData: number;
    confidencePct: number;
    description: string;
  };
  trend: Trend;
  updateCount: number;
  probChangeSinceLast: number;
  surfaceData: {
    soilMoisture: number;
    vegetationWaterContent: number;
    prevDayAod: number;
  };
  history: ProgressiveUpdate[];
  alertMessage: string;
}

// GET /api/v1/alerts/active
export interface TrackedAlert {
  lat: number;
  lon: number;
  locationName: string;
  targetDate: string;
  createdAt: string;
  updates: ProgressiveUpdate[];
  currentAlert: { level: AlertLevel; label: string; probability: number };
  trend: string;
}

export interface ActiveAlertsResponse {
  totalTracked: number;
  activeAlerts: number;
  predictions: TrackedAlert[];
}

// Local-only prototype subscription (no backend endpoint yet -- see api.ts)
export interface AlertSubscription {
  phone: string;
  lat: number;
  lon: number;
  locationName: string;
  threshold: AlertLevel;
}
