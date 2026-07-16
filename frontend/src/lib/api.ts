import { env } from '$env/dynamic/public';
import type { ActiveAlert, AuthState, DailyHorizonResponse, Forecast, HistoricalSnapshot, Location, Prediction, ProgressiveEvidence, RiskLevel } from './types';

const base = (env.PUBLIC_API_BASE_URL || 'https://saheldust-backend.onrender.com').replace(/\/$/, '');
const timeoutMs = 45_000;

function alertLevel(probability: number): RiskLevel {
	if (probability >= .7) return 'alert';
	if (probability >= .5) return 'warning';
	if (probability >= .3) return 'watch';
	return 'clear';
}

async function getJson(path: string) {
	const controller = new AbortController();
	const timeout = setTimeout(() => controller.abort(), timeoutMs);
	try {
		const response = await fetch(`${base}${path}`, { signal: controller.signal, credentials: 'include' });
		if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || `Request failed (${response.status})`);
		return await response.json();
	} finally { clearTimeout(timeout); }
}

async function postJson(path: string, body?: unknown) {
	const controller = new AbortController();
	const timeout = setTimeout(() => controller.abort(), timeoutMs);
	try {
		const response = await fetch(`${base}${path}`, {
			method: 'POST', credentials: 'include', signal: controller.signal,
			headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {})
		});
		const payload = await response.json().catch(() => ({}));
		if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : `Request failed (${response.status})`);
		return payload;
	} finally { clearTimeout(timeout); }
}

export async function requestOtp(phone: string, purpose: 'signup' | 'login', deviceId: string) {
	return postJson('/api/v1/auth/request-otp', { phone, purpose, device_id: deviceId });
}

export async function verifyOtp(challengeId: string, code: string, preferredLocation?: Location) {
	return postJson('/api/v1/auth/verify-otp', {
		challenge_id: challengeId, code,
		preferred_location: preferredLocation ? { name: `${preferredLocation.name}, ${preferredLocation.country}`, lat: preferredLocation.lat, lon: preferredLocation.lon } : null
	});
}

export async function getAuthState(): Promise<AuthState> {
	const d = await getJson('/api/v1/auth/me');
	if (!d.authenticated) return { authenticated: false };
	const user = d.user;
	return { authenticated: true, user: { phoneUid: user.phone_uid, preferredLocation: user.preferred_lat == null ? undefined : { name: user.preferred_location_name, country: '', lat: user.preferred_lat, lon: user.preferred_lon } } };
}

export async function logout() { return postJson('/api/v1/auth/logout'); }

async function deleteJson(path: string) {
	const response = await fetch(`${base}${path}`, { method: 'DELETE', credentials: 'include' });
	const payload = await response.json().catch(() => ({}));
	if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
	return payload;
}

export async function deleteAccount() { return deleteJson('/api/v1/auth/account'); }

export async function saveAlertSubscription(location: Location, threshold: 'watch' | 'warning' | 'alert') {
	const response = await fetch(`${base}/api/v1/subscriptions`, {
		method: 'PUT', credentials: 'include', headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ lat: location.lat, lon: location.lon, location_name: `${location.name}, ${location.country}`, threshold })
	});
	const payload = await response.json().catch(() => ({}));
	if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
	return payload;
}

export async function getNotifications() {
	const d = await getJson('/api/v1/notifications?limit=50');
	return d.notifications;
}

export async function getLatestPrediction(location: Location): Promise<Prediction> {
	const d = await getJson(`/api/v1/predictions/latest?lat=${location.lat}&lon=${location.lon}`);
	const x = d.prediction;
	return { lat: x.lat, lon: x.lon, locationName: x.location_name, probability: x.probability,
		riskLevel: x.alert_level, dustEvent: x.dust_event, predictionDate: x.target_date,
		dataSource: x.data_source, available: true,
		surfaceData: d.surface_data ? { soilMoisture: d.surface_data.soil_moisture, vegetationWaterContent: d.surface_data.vegetation_water_content, aod: d.surface_data.prev_day_aod } : undefined,
		inputQuality: d.evidence?.raw_payload?.input_quality ? { degraded: d.evidence.raw_payload.input_quality.degraded, warning: d.evidence.raw_payload.input_quality.warning, fields: d.evidence.raw_payload.input_quality } : undefined };
}

export async function getCurrentConditions(location: Location) {
	const d = await getJson(`/api/v1/conditions/current?lat=${location.lat}&lon=${location.lon}`);
	return d.current_conditions;
}

export async function getPrediction(location: Location): Promise<Prediction> {
	const d = await getJson(`/api/v1/predict/location?lat=${location.lat}&lon=${location.lon}`);
	const c = d.current_conditions;
	return {
		lat: d.lat, lon: d.lon, locationName: d.location_name, probability: d.probability,
		riskLevel: alertLevel(d.probability), dustEvent: d.dust_event,
		predictionDate: d.prediction_date, dataSource: d.data_source,
		conditions: c ? {
			observedAt: c.observed_at, windSpeedMs: c.wind_speed_ms, windSpeedKmh: c.wind_speed_kmh,
			windDirectionDeg: c.wind_direction_deg, temperatureC: c.temperature_c,
			surfacePressureHpa: c.surface_pressure_hpa, precipitationMm: c.precipitation_mm,
			dewpointC: c.dewpoint_c ?? 0,
			soilMoisture: c.soil_moisture ?? d.surface_data?.soil_moisture ?? 0,
			vegetationWaterContent: d.surface_data?.vegetation_water_content ?? 0,
			aod: d.surface_data?.prev_day_aod ?? 0
		} : undefined,
		surfaceData: d.surface_data ? {
			soilMoisture: d.surface_data.soil_moisture,
			vegetationWaterContent: d.surface_data.vegetation_water_content,
			aod: d.surface_data.prev_day_aod
		} : undefined,
		inputQuality: d.input_quality ? { degraded: d.input_quality.degraded, warning: d.input_quality.warning, fields: d.input_quality } : undefined,
		available: true
	};
}

export async function getForecast(location: Location): Promise<Forecast> {
	const d = await getJson(`/api/v1/forecast?lat=${location.lat}&lon=${location.lon}&days=3`);
	return { lat: d.lat, lon: d.lon, locationName: d.location_name, generatedAt: d.generated_at, days: d.days.map((x: any) => ({ date: x.date, probability: x.probability, risk: x.risk_level, dustEvent: x.dust_event })) };
}

export async function getProgressiveEvidence(location: Location): Promise<ProgressiveEvidence> {
	const d = await getJson(`/api/v1/predict/progressive?lat=${location.lat}&lon=${location.lon}`);
	const c = d.current_conditions;
	return {
		probability: d.probability, riskLevel: d.alert_level, targetDate: d.target_date,
		hoursUntilEvent: d.hours_until_event, confidencePct: d.data_composition.confidence_pct,
		observedHours: d.data_composition.hours_real_observations,
		forecastHours: d.data_composition.hours_forecast_data, trend: d.trend,
		soilMoisture: d.surface_data.soil_moisture,
		vegetationWaterContent: d.surface_data.vegetation_water_content,
		aod: d.surface_data.prev_day_aod, message: d.alert_message,
		conditions: c ? {
			observedAt: c.observed_at, windSpeedMs: c.wind_speed_ms, windSpeedKmh: c.wind_speed_kmh,
			windDirectionDeg: c.wind_direction_deg, temperatureC: c.temperature_c,
			surfacePressureHpa: c.surface_pressure_hpa, precipitationMm: c.precipitation_mm,
			dewpointC: c.dewpoint_c, soilMoisture: c.soil_moisture,
			vegetationWaterContent: c.vegetation_water_content, aod: c.aod
		} : undefined,
		inputQuality: d.input_quality ? { degraded: d.input_quality.degraded, warning: d.input_quality.warning } : undefined
	};
}

export async function getHistory(location: Location, date: string): Promise<HistoricalSnapshot[]> {
	const qs = new URLSearchParams({ lat: String(location.lat), lon: String(location.lon), date });
	const d = await getJson(`/api/v1/history?${qs}`);
	return d.snapshots.map((x: any) => ({ id: x.id, lat: x.lat, lon: x.lon, locationName: x.location_name, probability: x.probability, riskLevel: x.alert_level, dustEvent: x.dust_event, predictionDate: x.target_date, targetDate: x.target_date, recordedAt: x.recorded_at, dataSource: x.data_source, modelVersion: x.model_version, source: 'live' }));
}

export async function getRecentHistory(location: Location, limit = 10): Promise<HistoricalSnapshot[]> {
	const d = await getJson(`/api/v1/history/recent?lat=${location.lat}&lon=${location.lon}&limit=${limit}`);
	return d.snapshots.map((x: any) => ({ id: x.id, lat: x.lat, lon: x.lon, locationName: x.location_name, probability: x.probability, riskLevel: x.alert_level, dustEvent: x.dust_event, predictionDate: x.target_date, targetDate: x.target_date, recordedAt: x.recorded_at, dataSource: x.data_source, modelVersion: x.model_version, source: 'live' }));
}

export async function getDailyHorizons(location: Location): Promise<DailyHorizonResponse> {
	const d = await getJson(`/api/v1/predict/daily-horizons?lat=${location.lat}&lon=${location.lon}`);
	const c = d.current_conditions;
	return {
		lat: d.lat, lon: d.lon, locationName: d.location_name, referenceDate: d.reference_date,
		generatedAt: d.generated_at, modelVersion: d.model_version,
		conditions: {
			observedAt: c.observed_at, windSpeedMs: c.wind_speed_ms, windSpeedKmh: c.wind_speed_kmh,
			windDirectionDeg: c.wind_direction_deg, temperatureC: c.temperature_c,
			surfacePressureHpa: c.surface_pressure_hpa, precipitationMm: c.precipitation_mm,
			dewpointC: c.dewpoint_c ?? 0, soilMoisture: c.soil_moisture ?? d.surface_data.soil_moisture,
			vegetationWaterContent: d.surface_data.vegetation_water_content, aod: d.surface_data.prev_day_aod
		},
		horizons: d.horizons.map((x: any) => ({ horizon: x.horizon, targetDate: x.target_date,
			approximateLeadTime: x.approximate_lead_time, probability: x.probability,
			riskLevel: x.alert_level, dustEvent: x.dust_event }))
	};
}

export async function getActiveAlerts(): Promise<ActiveAlert[]> {
	const d = await getJson('/api/v1/alerts/active');
	return d.predictions.map((x: any) => ({
		lat: x.lat, lon: x.lon, locationName: x.location_name, targetDate: x.target_date,
		currentAlert: x.current_alert, trend: x.trend,
		updates: x.updates.map((u: any) => ({ timestamp: u.timestamp, probability: u.probability, alertLevel: u.alert_level, confidence: u.confidence }))
	}));
}

export function demoPrediction(location: Location): Prediction {
	return { ...location, locationName: `${location.name}, ${location.country}`, probability: 0, riskLevel: 'clear', dustEvent: false, predictionDate: new Date().toISOString().slice(0, 10), dataSource: 'Unavailable', available: false };
}
