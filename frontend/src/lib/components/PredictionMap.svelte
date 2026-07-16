<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import type { Conditions, Location, Prediction } from '$lib/types';

	export let location: Location;
	export let prediction: Prediction;
	export let conditions: Conditions | undefined;
	let container: HTMLDivElement;
	let map: maplibregl.Map;
	let marker: maplibregl.Marker;
	const riskColor = { clear: '#248a3d', watch: '#b07900', warning: '#c93400', alert: '#d70015' };

	function destination(lon: number, lat: number, bearing: number, distanceKm: number) {
		const radius = 6371, angular = distanceKm / radius, brng = bearing * Math.PI / 180;
		const phi1 = lat * Math.PI / 180, lambda1 = lon * Math.PI / 180;
		const phi2 = Math.asin(Math.sin(phi1) * Math.cos(angular) + Math.cos(phi1) * Math.sin(angular) * Math.cos(brng));
		const lambda2 = lambda1 + Math.atan2(Math.sin(brng) * Math.sin(angular) * Math.cos(phi1), Math.cos(angular) - Math.sin(phi1) * Math.sin(phi2));
		return [lambda2 * 180 / Math.PI, phi2 * 180 / Math.PI];
	}

	function showTransportCorridor() {
		if (!map?.loaded() || !conditions) return;
		const downwind = (conditions.windDirectionDeg + 180) % 360;
		const length = Math.min(450, Math.max(80, conditions.windSpeedKmh * 9));
		const data: GeoJSON.Feature<GeoJSON.LineString> = { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [[location.lon, location.lat], destination(location.lon, location.lat, downwind, length)] } };
		const source = map.getSource('transport') as maplibregl.GeoJSONSource | undefined;
		if (source) source.setData(data); else {
			map.addSource('transport', { type: 'geojson', data });
			map.addLayer({ id: 'transport-glow', type: 'line', source: 'transport', paint: { 'line-color': riskColor[prediction.riskLevel], 'line-width': 18, 'line-opacity': .13, 'line-blur': 8 } });
			map.addLayer({ id: 'transport-line', type: 'line', source: 'transport', paint: { 'line-color': riskColor[prediction.riskLevel], 'line-width': 4, 'line-opacity': .8, 'line-dasharray': [2, 2] } });
		}
	}

	const lightStyle: maplibregl.StyleSpecification = { version: 8, sources: { carto: { type: 'raster', tiles: ['https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png','https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'], tileSize: 256, attribution: '&copy; OpenStreetMap &copy; CARTO' } }, layers: [{ id: 'carto', type: 'raster', source: 'carto', paint: { 'raster-saturation': -.45, 'raster-contrast': -.08 } }] };

	function showPoint() {
		if (!map?.loaded()) return;
		marker?.remove();
		const el = document.createElement('button');
		el.className = 'risk-marker';
		el.style.setProperty('--marker', riskColor[prediction.riskLevel]);
		const label = prediction.available === false ? 'Unavailable' : `${Math.round(prediction.probability * 100)}%`;
		el.setAttribute('aria-label', prediction.available === false ? `${prediction.locationName}, prediction unavailable` : `${prediction.locationName}, ${label} dust risk`);
		el.innerHTML = `<span>${label}</span>`;
		marker = new maplibregl.Marker({ element: el }).setLngLat([location.lon, location.lat]).setPopup(new maplibregl.Popup({ offset: 26, closeButton: false }).setHTML(`<strong>${prediction.locationName}</strong><p>${prediction.available === false ? 'Prediction unavailable' : `${label} probability · ${prediction.riskLevel}`}</p>`)).addTo(map);
		showTransportCorridor();
		map.flyTo({ center: [location.lon, location.lat], zoom: 5.2, duration: 850 });
	}

	onMount(() => {
		map = new maplibregl.Map({ container, style: lightStyle, center: [location.lon, location.lat], zoom: 5.2, antialias: true, attributionControl: false });
		map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
		map.addControl(new maplibregl.AttributionControl({ compact: true }));
		map.on('load', showPoint);
	});
	$: if (map && location && prediction) showPoint();
	onDestroy(() => map?.remove());
</script>

<div class="map-shell"><div bind:this={container} class="map" aria-label="Dust-risk map centred on {location.name}"></div>{#if conditions}<div class="corridor-note"><strong>Wind transport corridor</strong><span>{conditions.windSpeedKmh} km/h · toward {Math.round((conditions.windDirectionDeg + 180) % 360)}°</span><small>Directional weather guidance—not a predicted storm boundary or evacuation route.</small></div>{/if}</div>

<style>
	.map-shell,.map { width: 100%; height: 100%; }.map-shell{position:relative}.map { min-height: 420px; background: #e8ebed; }.corridor-note{position:absolute;z-index:2;right:12px;bottom:28px;left:12px;padding:12px 14px;display:grid;gap:3px;border:1px solid rgba(255,255,255,.7);border-radius:16px;color:#17171a;background:rgba(255,255,255,.86);box-shadow:0 10px 30px rgba(15,23,42,.12);backdrop-filter:blur(18px)}.corridor-note span,.corridor-note small{color:#626269}.corridor-note small{line-height:1.4}
	:global(.risk-marker) { position: relative; width: 64px; height: 64px; display: grid; place-items: center; border: 6px solid color-mix(in srgb, var(--marker) 22%, white); border-radius: 50%; color: white; background: var(--marker); box-shadow: 0 10px 30px color-mix(in srgb, var(--marker) 40%, transparent); cursor: pointer; }
	:global(.risk-marker::after) { content: ''; position: absolute; inset: -16px; border: 2px solid color-mix(in srgb, var(--marker) 36%, transparent); border-radius: 50%; animation: ripple 2.7s ease-out infinite; }
	:global(.risk-marker span) { font-size: .85rem; font-weight: 750; font-variant-numeric: tabular-nums; }
	:global(.maplibregl-popup-content) { padding: 15px 17px; border: 1px solid rgba(255,255,255,.7); border-radius: 18px; color: #17171a; background: rgba(255,255,255,.82); box-shadow: 0 14px 40px rgba(15,23,42,.12); backdrop-filter: blur(20px); }
	:global(.maplibregl-popup-content p) { margin: 5px 0 0; color: #626269; font-size: .78rem; }
	:global(.maplibregl-ctrl-group) { overflow: hidden; border-radius: 14px; box-shadow: 0 8px 26px rgba(15,23,42,.12); }
	@keyframes ripple { to { opacity: 0; transform: scale(1.32); } }
</style>
