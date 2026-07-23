import { env } from '$env/dynamic/public';
import type { ActiveAlert, AuthState, DailyHorizonResponse, HistoricalSnapshot, Location, Prediction } from './types';

const base = (env.PUBLIC_API_BASE_URL || 'https://saheldust-backend.onrender.com').replace(/\/$/, '');
const timeoutMs = 75_000;

async function getJson(path: string, requestTimeoutMs = timeoutMs) {
	const controller = new AbortController();
	const timeout = setTimeout(() => controller.abort(), requestTimeoutMs);
	try {
		const response = await fetch(`${base}${path}`, { signal: controller.signal, credentials: 'include' });
		if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || `Request failed (${response.status})`);
		return await response.json();
	} finally { clearTimeout(timeout); }
}

function coveredPlace(x: any): Location {
	return {
		name: x.name, country: x.country, lat: Number(x.lat), lon: Number(x.lon),
		countryCode: x.country_code, placeType: x.place_type, coverageStatus: x.coverage_status,
		forecastLat: Number(x.forecast_lat ?? x.lat), forecastLon: Number(x.forecast_lon ?? x.lon)
	};
}

function forecastCoordinates(location: Location) {
	return { lat: location.forecastLat ?? location.lat, lon: location.forecastLon ?? location.lon };
}

export async function getCoveredLocations(): Promise<Location[]> {
	const data = await getJson('/api/v1/coverage/places?limit=500');
	return Array.isArray(data.places) ? data.places.map(coveredPlace) : [];
}

export async function getNearestCoveredLocation(lat: number, lon: number): Promise<Location> {
	const data = await getJson(`/api/v1/coverage/nearest?lat=${lat}&lon=${lon}`);
	return coveredPlace(data.place);
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

export async function createFirebaseSession(idToken: string, purpose: 'signup' | 'login', deviceId: string, preferredLocation?: Location) {
	return postJson('/api/v1/auth/firebase/session', {
		id_token: idToken, purpose, device_id: deviceId,
		preferred_location: preferredLocation ? { name: `${preferredLocation.name}, ${preferredLocation.country}`, lat: preferredLocation.forecastLat ?? preferredLocation.lat, lon: preferredLocation.forecastLon ?? preferredLocation.lon } : null
	});
}

export async function deleteFirebaseAccount(idToken: string) {
	return postJson('/api/v1/auth/firebase/account/delete', { id_token: idToken });
}

export async function getAuthState(): Promise<AuthState> {
	const d = await getJson('/api/v1/auth/me');
	if (!d.authenticated) return { authenticated: false };
	const user = d.user;
	return { authenticated: true, user: { phoneUid: user.phone_uid, authProvider: user.auth_provider, preferredLocation: user.preferred_lat == null ? undefined : { name: user.preferred_location_name, country: '', lat: user.preferred_lat, lon: user.preferred_lon } } };
}

export async function logout() { return postJson('/api/v1/auth/logout'); }

export async function requestAccountDeletionOtp(deviceId: string) {
	return postJson('/api/v1/auth/account/delete-otp', { device_id: deviceId });
}

export async function confirmAccountDeletion(challengeId: string, code: string) {
	return postJson('/api/v1/auth/account/confirm-delete', { challenge_id: challengeId, code });
}

export async function saveAlertSubscription(location: Location, threshold: 'watch' | 'warning' | 'alert') {
	const point = forecastCoordinates(location);
	const response = await fetch(`${base}/api/v1/subscriptions`, {
		method: 'PUT', credentials: 'include', headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ lat: point.lat, lon: point.lon, location_name: `${location.name}, ${location.country}`, threshold })
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
	const point = forecastCoordinates(location);
	const d = await getJson(`/api/v1/predictions/latest?lat=${point.lat}&lon=${point.lon}`, 3_000);
	const x = d.prediction;
	const c = d.current_conditions;
	const fieldEvidence = Array.isArray(d.environmental_evidence) ? d.environmental_evidence.map((item: any) => ({
		variableName: item.variable_name, value: item.value == null ? null : Number(item.value),
		unit: item.unit, provider: item.provider, kind: item.evidence_kind,
		measuredAt: item.measured_at, availableAt: item.available_at,
		qualityStatus: item.quality_status, isFallback: Boolean(item.is_fallback)
	})) : [];
	const evidenceByName = new Map(fieldEvidence.map((item: any) => [item.variableName, item]));
	const soilEvidence: any = evidenceByName.get('soil_moisture');
	const aodEvidence: any = evidenceByName.get('previous_day_aod');
	const soilValue = soilEvidence
		? (soilEvidence.qualityStatus === 'valid' ? soilEvidence.value : null)
		: c?.soil_moisture;
	const aodValue = aodEvidence
		? (aodEvidence.qualityStatus === 'valid' ? aodEvidence.value : null)
		: c?.aod;
	return { lat: x.lat, lon: x.lon, locationName: x.location_name, probability: x.probability,
		riskLevel: x.alert_level, dustEvent: x.dust_event, predictionDate: x.target_date,
		dataSource: x.data_source, available: true,
		conditions: c ? { observedAt: c.observed_at, windSpeedMs: c.wind_speed_ms, windSpeedKmh: c.wind_speed_kmh,
			windDirectionDeg: c.wind_direction_deg, temperatureC: c.temperature_c,
			surfacePressureHpa: c.surface_pressure_hpa, precipitationMm: c.precipitation_mm,
			dewpointC: c.dewpoint_c ?? 0, soilMoisture: soilValue,
			vegetationWaterContent: c.vegetation_water_content, aod: aodValue } : undefined,
		surfaceData: d.surface_data ? { soilMoisture: soilValue, vegetationWaterContent: d.surface_data.vegetation_water_content, aod: aodValue } : undefined,
		inputQuality: d.evidence?.raw_payload?.input_quality ? { degraded: d.evidence.raw_payload.input_quality.degraded, warning: d.evidence.raw_payload.input_quality.warning, fields: d.evidence.raw_payload.input_quality } : undefined,
		freshness: d.freshness ? { recordedAt: d.freshness.recorded_at, ageMinutes: d.freshness.age_minutes, stale: d.freshness.stale, source: d.freshness.source } : undefined,
		environmentalEvidence: fieldEvidence,
		evidenceSummary: {
			observedFraction: Number(x.observed_fraction ?? 0),
			forecastFraction: Number(x.forecast_fraction ?? 0),
			inputCompleteness: Number(x.input_completeness ?? 0)
		} };
}

export async function getCurrentConditions(location: Location) {
	const point = forecastCoordinates(location);
	const d = await getJson(`/api/v1/conditions/current?lat=${point.lat}&lon=${point.lon}`);
	return d.current_conditions;
}

export async function getHistory(location: Location, date: string): Promise<HistoricalSnapshot[]> {
	const point = forecastCoordinates(location);
	const qs = new URLSearchParams({ lat: String(point.lat), lon: String(point.lon), date });
	const d = await getJson(`/api/v1/history?${qs}`);
	return d.snapshots.map((x: any) => ({ id: x.id, lat: x.lat, lon: x.lon, locationName: x.location_name, probability: x.probability, riskLevel: x.alert_level, dustEvent: x.dust_event, predictionDate: x.target_date, targetDate: x.target_date, recordedAt: x.recorded_at, dataSource: x.data_source, modelVersion: x.model_version, source: 'live' }));
}

export async function getRecentHistory(location: Location, limit = 10): Promise<HistoricalSnapshot[]> {
	const point = forecastCoordinates(location);
	const d = await getJson(`/api/v1/history/recent?lat=${point.lat}&lon=${point.lon}&limit=${limit}`);
	return d.snapshots.map((x: any) => ({ id: x.id, lat: x.lat, lon: x.lon, locationName: x.location_name, probability: x.probability, riskLevel: x.alert_level, dustEvent: x.dust_event, predictionDate: x.target_date, targetDate: x.target_date, recordedAt: x.recorded_at, dataSource: x.data_source, modelVersion: x.model_version, source: 'live' }));
}

export async function getDailyHorizons(location: Location): Promise<DailyHorizonResponse> {
	const point = forecastCoordinates(location);
	const d = await getJson(`/api/v1/predict/daily-horizons?lat=${point.lat}&lon=${point.lon}`);
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
