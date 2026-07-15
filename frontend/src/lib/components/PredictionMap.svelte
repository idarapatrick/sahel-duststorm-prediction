<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import type { Location, Prediction } from '$lib/types';

	export let location: Location;
	export let prediction: Prediction;
	let container: HTMLDivElement;
	let map: maplibregl.Map;
	let marker: maplibregl.Marker;
	const riskColor = { clear: '#248a3d', watch: '#b07900', warning: '#c93400', alert: '#d70015' };

	const lightStyle: maplibregl.StyleSpecification = { version: 8, sources: { carto: { type: 'raster', tiles: ['https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png','https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'], tileSize: 256, attribution: '&copy; OpenStreetMap &copy; CARTO' } }, layers: [{ id: 'carto', type: 'raster', source: 'carto', paint: { 'raster-saturation': -.45, 'raster-contrast': -.08 } }] };

	function showPoint() {
		if (!map?.loaded()) return;
		marker?.remove();
		const el = document.createElement('button');
		el.className = 'risk-marker';
		el.style.setProperty('--marker', riskColor[prediction.riskLevel]);
		el.setAttribute('aria-label', `${prediction.locationName}, ${Math.round(prediction.probability * 100)} percent dust risk`);
		el.innerHTML = `<span>${Math.round(prediction.probability * 100)}%</span>`;
		marker = new maplibregl.Marker({ element: el }).setLngLat([location.lon, location.lat]).setPopup(new maplibregl.Popup({ offset: 26, closeButton: false }).setHTML(`<strong>${prediction.locationName}</strong><p>${Math.round(prediction.probability * 100)}% probability · ${prediction.riskLevel}</p>`)).addTo(map);
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

<div bind:this={container} class="map" aria-label="Dust-risk map centred on {location.name}"></div>

<style>
	.map { width: 100%; height: 100%; min-height: 420px; background: #e8ebed; }
	:global(.risk-marker) { position: relative; width: 64px; height: 64px; display: grid; place-items: center; border: 6px solid color-mix(in srgb, var(--marker) 22%, white); border-radius: 50%; color: white; background: var(--marker); box-shadow: 0 10px 30px color-mix(in srgb, var(--marker) 40%, transparent); cursor: pointer; }
	:global(.risk-marker::after) { content: ''; position: absolute; inset: -16px; border: 2px solid color-mix(in srgb, var(--marker) 36%, transparent); border-radius: 50%; animation: ripple 2.7s ease-out infinite; }
	:global(.risk-marker span) { font-size: .85rem; font-weight: 750; font-variant-numeric: tabular-nums; }
	:global(.maplibregl-popup-content) { padding: 15px 17px; border: 1px solid rgba(255,255,255,.7); border-radius: 18px; color: #17171a; background: rgba(255,255,255,.82); box-shadow: 0 14px 40px rgba(15,23,42,.12); backdrop-filter: blur(20px); }
	:global(.maplibregl-popup-content p) { margin: 5px 0 0; color: #626269; font-size: .78rem; }
	:global(.maplibregl-ctrl-group) { overflow: hidden; border-radius: 14px; box-shadow: 0 8px 26px rgba(15,23,42,.12); }
	@keyframes ripple { to { opacity: 0; transform: scale(1.32); } }
</style>
