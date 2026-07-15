export type RiskLevel = 'clear' | 'watch' | 'warning' | 'alert';

export interface Location { name: string; country: string; lat: number; lon: number; }
export interface AuthUser { phoneUid: string; preferredLocation?: Location; }
export interface AuthState { authenticated: boolean; user?: AuthUser; }
export interface ForecastDay { date: string; probability: number; risk: string; dustEvent: boolean; }
export interface Forecast { lat: number; lon: number; locationName: string; generatedAt: string; days: ForecastDay[]; }
export interface Prediction {
	lat: number; lon: number; locationName: string; probability: number; riskLevel: RiskLevel;
	dustEvent: boolean; predictionDate: string; dataSource: string;
	conditions?: Conditions;
	surfaceData?: { soilMoisture: number; vegetationWaterContent: number; aod: number };
}
export interface HistoricalSnapshot extends Prediction {
	id: string; recordedAt: string; targetDate: string; modelVersion?: string; source: 'live' | 'demo';
}

export interface Conditions {
	observedAt: string; windSpeedMs: number; windSpeedKmh: number; windDirectionDeg: number;
	temperatureC: number; surfacePressureHpa: number; precipitationMm: number;
	dewpointC: number; soilMoisture: number; vegetationWaterContent: number; aod: number;
}
export interface DailyHorizonPrediction {
	horizon: 'day+0' | 'day+1' | 'day+2'; targetDate: string; approximateLeadTime: string;
	probability: number; riskLevel: RiskLevel; dustEvent: boolean;
}
export interface DailyHorizonResponse {
	lat: number; lon: number; locationName: string; referenceDate: string; generatedAt: string;
	modelVersion?: string; conditions: Conditions; horizons: DailyHorizonPrediction[];
}
export interface AlertUpdate { timestamp: string; probability: number; alertLevel: RiskLevel; confidence: number; }
export interface ActiveAlert { lat: number; lon: number; locationName: string; targetDate: string; currentAlert: { level: RiskLevel; label: string; probability: number }; updates: AlertUpdate[]; trend: string; }
export interface ProgressiveEvidence {
	probability: number; riskLevel: RiskLevel; targetDate: string; hoursUntilEvent: number;
	confidencePct: number; observedHours: number; forecastHours: number; trend: string;
	soilMoisture: number; vegetationWaterContent: number; aod: number; message: string;
	conditions?: Conditions;
}
