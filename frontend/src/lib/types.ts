export type RiskLevel = 'clear' | 'watch' | 'warning' | 'alert';

export interface Location {
	name: string; country: string; lat: number; lon: number;
	countryCode?: string; placeType?: 'city' | 'town' | 'village' | 'community';
	coverageStatus?: 'validated' | 'operational' | 'provisional';
	forecastLat?: number; forecastLon?: number;
}
export interface AuthUser { phoneUid: string; authProvider?: 'firebase' | 'legacy_otp'; preferredLocation?: Location; }
export interface AuthState { authenticated: boolean; user?: AuthUser; }
export interface ForecastDay { date: string; probability: number; risk: string; dustEvent: boolean; }
export interface Forecast { lat: number; lon: number; locationName: string; generatedAt: string; days: ForecastDay[]; }
export interface Prediction {
	lat: number; lon: number; locationName: string; probability: number; riskLevel: RiskLevel;
	dustEvent: boolean; predictionDate: string; dataSource: string;
	conditions?: Conditions;
	surfaceData?: { soilMoisture: number | null; vegetationWaterContent: number | null; aod: number | null };
	inputQuality?: { degraded: boolean; warning?: string; fields?: Record<string, any> };
	freshness?: { recordedAt: string; ageMinutes: number; stale: boolean; source: string };
	environmentalEvidence?: EnvironmentalEvidence[];
	evidenceSummary?: { observedFraction: number; forecastFraction: number; inputCompleteness: number };
	outlooks?: CentralOutlook[];
	available?: boolean;
}
export interface CentralOutlook {
	targetDate: string; probability: number; riskLevel: RiskLevel; recordedAt: string;
	inputCompleteness?: number;
}
export interface EnvironmentalEvidence {
	variableName: string; value: number | null; unit?: string; provider: string;
	kind: 'observation' | 'analysis' | 'forecast' | 'delayed_observation' | 'fallback' | 'missing';
	measuredAt?: string; availableAt: string; qualityStatus: string; isFallback: boolean;
}
export interface HistoricalSnapshot extends Prediction {
	id: string; recordedAt: string; targetDate: string; modelVersion?: string; source: 'live' | 'demo';
}

export interface Conditions {
	observedAt: string; windSpeedMs: number | null; windSpeedKmh: number | null; windDirectionDeg: number | null;
	temperatureC: number | null; surfacePressureHpa: number | null; precipitationMm: number | null;
	dewpointC: number | null; soilMoisture: number | null; vegetationWaterContent: number | null; aod: number | null;
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
	inputQuality?: { degraded: boolean; warning?: string };
}
