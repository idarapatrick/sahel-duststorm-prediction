<script lang="ts">
	import { onMount } from 'svelte';
	import { Activity, ArrowRight, Bell, CalendarDays, Clock3, Droplets, Gauge, Info, Map, Navigation, Phone, Settings, ShieldCheck, Sparkles, Thermometer, Trash2, Wind } from 'lucide-svelte';
	import AppHeader from '$lib/components/AppHeader.svelte';
	import OnboardingFlow from '$lib/components/OnboardingFlow.svelte';
	import PredictionMap from '$lib/components/PredictionMap.svelte';
	import { DEFAULT_LOCATION, locations } from '$lib/locations';
	import { demoPrediction, getActiveAlerts, getAuthState, getForecast, getHistory, getPrediction, getProgressiveEvidence, getRecentHistory, logout } from '$lib/api';
	import type { ActiveAlert, AuthState, DailyHorizonResponse, Forecast, HistoricalSnapshot, Location, Prediction, ProgressiveEvidence } from '$lib/types';

	let selected = DEFAULT_LOCATION;
	let prediction: Prediction = demoPrediction(selected);
	let forecast: Forecast | null = null;
	let history: HistoricalSnapshot[] = [];
	let recentHistory: HistoricalSnapshot[] = [];
	let dailyHorizons: DailyHorizonResponse | null = null;
	let progressive: ProgressiveEvidence | null = null;
	let selectedHorizon: 'day+0' | 'day+1' | 'day+2' = 'day+0';
	let activeAlerts: ActiveAlert[] = [];
	let linkedPhone = '';
	let phoneMessage = '';
	let authState: AuthState = { authenticated: false };
	let deviceId = '';
	let showSplash = true;
	let showOnboarding = false;
	let showAuth = false;
	let online = true;
	let loading = true;
	let historyLoading = false;
	let historyMessage = '';
	let activeTab: 'overview' | 'tracking' | 'history' | 'notifications' | 'settings' = 'overview';
	let searchDate = new Date(Date.now() - 14 * 86400000).toISOString().slice(0, 10);
	const today = new Date().toISOString().slice(0, 10);
	const minDate = new Date(Date.now() - 89 * 86400000).toISOString().slice(0, 10);
	const dailyHorizonNames = ['day+0', 'day+1', 'day+2'] as const;
	// Keep the UI visible but inactive until final model evaluation and ONNX export.
	const multiHorizonComingSoon = true;

	$: probability = Math.round(prediction.probability * 100);
	$: riskCopy = prediction.riskLevel === 'clear' ? 'No significant storm expected' : prediction.riskLevel === 'watch' ? 'Dust activity is possible' : prediction.riskLevel === 'warning' ? 'Dust storm conditions are likely' : 'Severe dust event expected';
	$: riskTone = prediction.riskLevel;
	$: nextDay = forecast?.days?.[0];
	$: horizon = dailyHorizons?.horizons.find((x) => x.horizon === selectedHorizon) || dailyHorizons?.horizons[0];
	$: conditions = dailyHorizons?.conditions || progressive?.conditions || prediction.conditions;

	async function loadLocation(location: Location) {
		selected = location; loading = true; history = []; historyMessage = '';
		const [predictionResult, forecastResult, progressiveResult] = await Promise.allSettled([
			getPrediction(location), getForecast(location), getProgressiveEvidence(location)
		]);
		if (predictionResult.status === 'fulfilled') {
			prediction = predictionResult.value;
			online = true;
		} else {
			prediction = demoPrediction(location);
			online = false;
		}
		forecast = forecastResult.status === 'fulfilled' ? forecastResult.value : null;
		progressive = progressiveResult.status === 'fulfilled' ? progressiveResult.value : null;
		dailyHorizons = null;
		loading = false; loadRecentHistory();
	}

	async function loadAlerts() {
		try { activeAlerts = await getActiveAlerts(); } catch { activeAlerts = []; }
	}

	async function signOut() {
		await logout(); authState = { authenticated: false }; linkedPhone = ''; phoneMessage = 'You are logged out. SMS alerts are disabled on this device.';
	}
	function finishOnboarding(event: CustomEvent<{ location: Location; phoneUid?: string }>) {
		selected = event.detail.location; localStorage.setItem('sahelwatch:location', JSON.stringify(selected));
		localStorage.setItem('sahelwatch:onboarded', 'true'); showOnboarding = false; showAuth = false;
		if (event.detail.phoneUid) { linkedPhone = event.detail.phoneUid; authState = { authenticated: true, user: { phoneUid: linkedPhone } }; }
		loadLocation(selected);
	}

	async function searchHistory() {
		historyLoading = true; historyMessage = '';
		try {
			history = await getHistory(selected, searchDate);
			historyMessage = history.length ? `${history.length} archived prediction${history.length === 1 ? '' : 's'} found.` : 'No prediction snapshot was recorded for this place and date.';
		} catch (error) {
			history = [];
			historyMessage = error instanceof Error ? error.message : 'Historical records are temporarily unavailable.';
		} finally { historyLoading = false; }
	}
	async function loadRecentHistory() { try { recentHistory = await getRecentHistory(selected, 10); } catch { recentHistory = []; } }

	onMount(() => {
		deviceId = localStorage.getItem('sahelwatch:device_id') || crypto.randomUUID(); localStorage.setItem('sahelwatch:device_id', deviceId);
		const savedLocation = localStorage.getItem('sahelwatch:location');
		if (savedLocation) { try { selected = JSON.parse(savedLocation); } catch { /* use default */ } }
		const alreadyShown = sessionStorage.getItem('sahelwatch:splash_shown') === 'true';
		showSplash = !alreadyShown; sessionStorage.setItem('sahelwatch:splash_shown', 'true');
		window.setTimeout(() => { showSplash = false; showOnboarding = localStorage.getItem('sahelwatch:onboarded') !== 'true'; }, alreadyShown ? 0 : 1200);
		getAuthState().then((state) => { authState = state; linkedPhone = state.user?.phoneUid || ''; }).catch(() => {});
		loadLocation(selected); loadAlerts(); loadRecentHistory();
		const reinforcementTimer = window.setInterval(() => loadLocation(selected), 10 * 60 * 60 * 1000);
		return () => window.clearInterval(reinforcementTimer);
	});
</script>

<svelte:head>
	<title>SahelWatch — Dust intelligence, hours ahead</title>
	<meta name="description" content="AI-powered dust and sand-storm forecasts for communities across the Sahel." />
</svelte:head>

{#if showSplash}
	<div class="splash" role="status" aria-label="Loading SahelWatch"><span><Wind size={34}/></span><strong>SahelWatch</strong><small>Preparing dust intelligence</small></div>
{:else if showOnboarding}
	<OnboardingFlow {deviceId} initialLocation={selected} on:complete={finishOnboarding}/>
{/if}
{#if showAuth}<OnboardingFlow {deviceId} initialLocation={selected} authOnly on:complete={finishOnboarding} on:close={() => showAuth=false}/>{/if}

<div class="app-shell">
	<AppHeader bind:selected {online} on:select={(e) => loadLocation(e.detail)} />

	<nav class="tabs glass" aria-label="Primary navigation">
		<button class:active={activeTab === 'overview'} on:click={() => activeTab = 'overview'}><Activity size={17}/>Overview</button>
		<button class:active={activeTab === 'tracking'} on:click={() => activeTab = 'tracking'}><Navigation size={17}/>Track</button>
		<button class:active={activeTab === 'history'} on:click={() => activeTab = 'history'}><CalendarDays size={17}/>History</button>
		<button class:active={activeTab === 'notifications'} on:click={() => { activeTab = 'notifications'; loadAlerts(); }}><Bell size={17}/>Alerts</button>
		<button class:active={activeTab === 'settings'} on:click={() => activeTab = 'settings'}><Settings size={17}/>Settings</button>
	</nav>

	<main id="main-content">
		{#if activeTab === 'overview'}
			<section class="hero" aria-labelledby="forecast-heading">
				<div class="hero-copy">
					<div class="place"><i class:demo={!online}></i>{online ? 'Live forecast' : 'Demonstration snapshot'} · {selected.name}, {selected.country}</div>
					<p class="eyebrow">Next 24–48 hours</p>
					<h1 id="forecast-heading">{riskCopy}<span class="risk-word {riskTone}">{probability}% risk</span></h1>
					<p class="summary">SahelWatch combines atmospheric forecasts and satellite surface observations to identify dust-emission conditions before they reach nearby communities.</p>
					<div class="hero-actions">
						<button class="primary" on:click={() => activeTab = 'tracking'}>Track this forecast <ArrowRight size={18}/></button>
						<button class="secondary" on:click={() => activeTab = 'history'}><CalendarDays size={18}/> Search past conditions</button>
					</div>
				</div>
				<div class="risk-orb {riskTone}" style={`--value:${prediction.probability}`} aria-label="{probability} percent dust-storm probability">
					<div><span>{loading ? '—' : probability}</span><small>%</small><p>{prediction.riskLevel}</p></div>
				</div>
			</section>

			<section class="metrics" aria-label="Environmental forecast indicators">
				<article class="glass"><span class="metric-icon"><Wind size={20}/></span><div><p>Wind speed</p><strong>{conditions ? `${conditions.windSpeedKmh} km/h` : 'Unavailable'}</strong><small>{conditions ? `${conditions.windDirectionDeg}° direction` : 'live model input'}</small></div></article>
				<article class="glass"><span class="metric-icon"><Thermometer size={20}/></span><div><p>Temperature</p><strong>{conditions ? `${conditions.temperatureC}°C` : 'Unavailable'}</strong><small>nearest current hour</small></div></article>
				<article class="glass"><span class="metric-icon"><Droplets size={20}/></span><div><p>Soil moisture</p><strong>{conditions ? `${(conditions.soilMoisture * 100).toFixed(1)}%` : progressive ? `${(progressive.soilMoisture * 100).toFixed(1)}%` : 'Unavailable'}</strong><small>surface emission signal</small></div></article>
				<article class="glass"><span class="metric-icon"><Gauge size={20}/></span><div><p>Atmosphere · AOD</p><strong>{conditions?.aod ? conditions.aod.toFixed(2) : progressive?.aod ? progressive.aod.toFixed(2) : 'Unavailable'}</strong><small>{progressive?.aod === 0 ? 'satellite value missing or zero' : 'satellite dust signal'}</small></div></article>
			</section>

			<section class="explanation glass">
				<span class="explanation-icon"><Sparkles size={22}/></span><div><p class="eyebrow">Prediction evidence</p><h2>{progressive ? `${Math.round(progressive.probability * 100)}% reinforced prediction · ${progressive.confidencePct}% observed-data completeness` : online ? 'Live model prediction received' : 'Prediction service is unreachable'}</h2><p>{progressive?.message || (online ? 'The probability above came from the deployed model.' : 'SahelWatch is showing a clearly labelled demonstration snapshot because the current prediction request failed.')}</p><small>{progressive ? `${progressive.observedHours} of 72 hours are observations; ${progressive.forecastHours} remain forecast data.` : 'No environmental values are invented on the client.'}</small></div>
			</section>

			<section class="forecast-strip glass">
				<div><p class="eyebrow">Next update</p><strong>Continuous monitoring</strong><small>Forecasts refine as observed data replaces forecast data.</small></div>
				{#each forecast?.days || [] as day}
					<div class="day"><span>{new Date(`${day.date}T12:00:00`).toLocaleDateString('en', { weekday: 'short' })}</span><strong>{Math.round(day.probability * 100)}%</strong><small>{day.risk}</small></div>
				{:else}<div class="day"><span>Tomorrow</span><strong>{nextDay ? Math.round(nextDay.probability * 100) : probability}%</strong><small>estimated</small></div>{/each}
			</section>

		{:else if activeTab === 'tracking'}
			<section class="subpage-head"><div><p class="eyebrow">Tracking</p><h1>Monitor {selected.name}</h1><p>Inspect the current risk and predicted 24–48 hour window.</p></div><select bind:value={selected} on:change={() => loadLocation(selected)} aria-label="Tracking location">{#each locations as location}<option value={location}>{location.name}, {location.country}</option>{/each}</select></section>
			<div class="horizon-coming-soon" aria-disabled="true">
				<div class="horizon-picker glass" aria-label="Daily prediction horizons — coming soon">
					{#each dailyHorizonNames as day}<button disabled={multiHorizonComingSoon || !dailyHorizons} title="Coming soon after final model evaluation and ONNX export" class:active={!multiHorizonComingSoon && Boolean(dailyHorizons) && selectedHorizon === day} on:click={() => selectedHorizon = day}>{day}</button>{/each}
				</div>
				<span>Coming soon</span>
			</div>
			<section class="tracking-grid">
				<div class="tracking-map glass"><PredictionMap location={selected} {prediction}/></div>
				<aside class="detail glass"><div class="detail-top"><span class="badge {horizon?.riskLevel || riskTone}">{horizon?.riskLevel || prediction.riskLevel}</span><small>{horizon?.targetDate || prediction.predictionDate}</small></div><h2>{horizon ? Math.round(horizon.probability * 100) : probability}% probability</h2><p>{horizon ? `${horizon.horizon} covers ${horizon.approximateLeadTime}.` : riskCopy}</p><dl><div><dt><Clock3 size={17}/>Daily horizon</dt><dd>{horizon?.horizon || 'Single-head model'}</dd></div><div><dt><Activity size={17}/>Approximate lead</dt><dd>{horizon?.approximateLeadTime || 'Not available'}</dd></div><div><dt><ShieldCheck size={17}/>Supervision</dt><dd>Daily MODIS AOD</dd></div><div><dt><Map size={17}/>Coordinates</dt><dd>{selected.lat.toFixed(2)}°, {selected.lon.toFixed(2)}°</dd></div></dl><div class="notice"><Info size={18}/><p>The horizons are calendar-day outputs. SahelWatch does not claim independent 12h/24h/36h/48h clock-hour labels.</p></div></aside>
			</section>

		{:else if activeTab === 'history'}
			<section class="history-page">
				<div class="subpage-head"><div><p class="eyebrow">90-day archive</p><h1>Look back with context</h1><p>Search prediction snapshots that SahelWatch actually recorded—never reconstructed or invented conditions.</p></div></div>
				{#if recentHistory.length}<div class="recent-history"><p class="eyebrow">Last 10 predictions for {selected.name}</p>{#each recentHistory as item}<article class="history-result glass"><div><strong>{new Date(item.recordedAt).toLocaleString()}</strong><p>Target {item.targetDate}</p></div><div class="historical-risk {item.riskLevel}"><strong>{Math.round(item.probability * 100)}%</strong><span>{item.riskLevel}</span></div></article>{/each}</div>{/if}
				<form class="history-form glass" on:submit|preventDefault={searchHistory}>
					<label><span>Covered location</span><select bind:value={selected}>{#each locations as location}<option value={location}>{location.name}, {location.country}</option>{/each}</select></label>
					<label><span>Date</span><input type="date" bind:value={searchDate} min={minDate} max={today}/></label>
					<button class="primary" disabled={historyLoading}>{historyLoading ? 'Searching…' : 'Search archive'} <ArrowRight size={18}/></button>
				</form>
				<div class="coverage-note"><Info size={18}/><p><strong>Coverage note:</strong> Ilorin is south of the currently validated 10–25°N model boundary. SahelWatch will not present unvalidated results for it.</p></div>
				{#if historyMessage}<p class="history-message" role="status">{historyMessage}</p>{/if}
				{#each history as item}
					<article class="history-result glass"><div><p class="eyebrow">Recorded {new Date(item.recordedAt).toLocaleString()}</p><h2>{item.locationName}</h2><p>Prediction target: {item.targetDate}</p></div><div class="historical-risk {item.riskLevel}"><strong>{Math.round(item.probability * 100)}%</strong><span>{item.riskLevel}</span></div></article>
				{/each}
			</section>
		{:else if activeTab === 'notifications'}
			<section class="utility-page">
				<div class="subpage-head"><div><p class="eyebrow">Broadcast centre</p><h1>Notifications & alerts</h1><p>Risk changes and high-confidence storm broadcasts appear here and as in-app banners.</p></div></div>
				{#if !linkedPhone}<div class="offline-callout glass"><Phone size={22}/><div><strong>Offline alerts are not active</strong><p>Link a phone number in Settings to receive SMS broadcasts when you do not have internet access.</p></div><button on:click={() => activeTab = 'settings'}>Link phone</button></div>{/if}
				<div class="notification-list">
					{#each activeAlerts.flatMap((a) => a.updates.map((u) => ({ ...u, locationName: a.locationName }))).sort((a,b) => b.timestamp.localeCompare(a.timestamp)).slice(0, 20) as item}
						<article class="notification glass"><span class="notification-mark {item.alertLevel}"><Bell size={18}/></span><div><strong>{item.locationName}: {item.alertLevel}</strong><p>{Math.round(item.probability * 100)}% probability · {item.confidence}% observed-data confidence</p><small>{new Date(item.timestamp).toLocaleString()}</small></div></article>
					{:else}<div class="empty glass"><Bell size={28}/><h2>No broadcasts yet</h2><p>New risk-level changes will be recorded here.</p></div>{/each}
				</div>
			</section>
		{:else}
			<section class="utility-page settings-page">
				<div class="subpage-head"><div><p class="eyebrow">Personalisation</p><h1>Settings</h1><p>Your phone number is the only personal information SahelWatch needs.</p></div></div>
				<section class="settings-card glass"><div class="settings-title"><span><Phone size={21}/></span><div><h2>Phone account & SMS alerts</h2><p>A verified international number is your unique account ID. Phone linking is optional, but SMS alerts require it.</p></div></div>{#if linkedPhone}<div class="linked"><ShieldCheck size={18}/><span>+{linkedPhone}</span><button class="danger" on:click={signOut}>Log out</button></div><button class="secondary account-switch" on:click={async () => { await signOut(); showAuth=true; }}>Log in with another number</button>{:else}<button class="primary account-link" on:click={() => showAuth=true}>Link phone or log in</button>{/if}{#if phoneMessage}<p class="form-message" role="status">{phoneMessage}</p>{/if}</section>
				<section class="legal glass"><a href="/privacy">Privacy policy <ArrowRight size={17}/></a><a href="/terms">Terms of use <ArrowRight size={17}/></a><button class="danger-row"><Trash2 size={17}/>Delete account and alert records</button></section>
			</section>
		{/if}
	</main>
	<footer><span>SahelWatch</span><p>Low-cost environmental intelligence for the African Sahel.</p><small>Research forecast · Not an official emergency warning</small></footer>
</div>

<style>
	.splash{position:fixed;z-index:1100;inset:0;display:grid;place-content:center;justify-items:center;background:var(--bg);color:var(--text)}.splash span{width:74px;height:74px;display:grid;place-items:center;border-radius:24px;color:white;background:var(--blue);box-shadow:0 22px 50px rgba(0,122,255,.25)}.splash strong{margin-top:18px;font-size:1.55rem;letter-spacing:-.04em}.splash small{margin-top:6px;color:var(--text-secondary)}
	.app-shell { width: min(1480px, calc(100% - 28px)); margin: 0 auto; padding: 14px 0 28px; }
	.tabs { width: max-content; margin: 16px auto 0; padding: 5px; display: flex; gap: 3px; border-radius: var(--radius-pill); }
	.tabs button { min-height: 42px; padding: 0 16px; display: flex; align-items: center; gap: 7px; border: 0; border-radius: var(--radius-pill); color: var(--text-secondary); background: transparent; cursor: pointer; transition: var(--ease); }
	.tabs button.active { color: var(--text); background: var(--surface-solid); box-shadow: var(--shadow-sm); }
	main { min-height: 70dvh; }
	.hero { min-height: 470px; padding: clamp(58px, 8vw, 120px) clamp(8px, 7vw, 100px) 58px; display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(260px, .8fr); align-items: center; gap: 54px; }
	.place { width: max-content; margin-bottom: 28px; padding: 8px 12px; display: flex; align-items: center; gap: 8px; border: 1px solid var(--border); border-radius: var(--radius-pill); color: var(--text-secondary); background: var(--surface); font-size: .76rem; font-weight: 600; }
	.place i { width: 8px; height: 8px; border-radius: 50%; background: var(--green); }.place i.demo { background: var(--orange); }
	h1, h2, p { margin-top: 0; }
	.hero h1 { max-width: 780px; margin-bottom: 20px; font-size: clamp(2.6rem, 6vw, 5.7rem); line-height: .98; letter-spacing: -.065em; }
	.risk-word { display: block; margin-top: 12px; }.risk-word.clear { color: var(--green); }.risk-word.watch { color: var(--yellow); }.risk-word.warning { color: var(--orange); }.risk-word.alert { color: var(--red); }
	.summary { max-width: 660px; color: var(--text-secondary); font-size: clamp(1rem, 1.4vw, 1.16rem); line-height: 1.65; }
	.hero-actions { margin-top: 28px; display: flex; flex-wrap: wrap; gap: 10px; }
	.primary, .secondary { min-height: 48px; padding: 0 18px; display: inline-flex; align-items: center; justify-content: center; gap: 9px; border: 0; border-radius: var(--radius-pill); cursor: pointer; transition: transform var(--ease), box-shadow var(--ease); }
	.primary { color: white; background: var(--blue); box-shadow: 0 10px 26px rgba(0,122,255,.22); }.primary:hover { transform: translateY(-1px); box-shadow: 0 14px 32px rgba(0,122,255,.3); }.primary:disabled { opacity: .55; cursor: wait; }
	.secondary { border: 1px solid var(--border); background: var(--surface); }
	.risk-orb { justify-self: center; width: clamp(230px, 27vw, 390px); aspect-ratio: 1; padding: 24px; display: grid; place-items: center; border-radius: 50%; background: conic-gradient(var(--tone) calc(var(--value, .34) * 1turn), color-mix(in srgb, var(--tone) 12%, transparent) 0); box-shadow: 0 30px 80px color-mix(in srgb, var(--tone) 16%, transparent); }
	.risk-orb.clear { --tone: var(--green); }.risk-orb.watch { --tone: var(--yellow); }.risk-orb.warning { --tone: var(--orange); }.risk-orb.alert { --tone: var(--red); }
	.risk-orb > div { width: 88%; aspect-ratio: 1; display: grid; place-content: center; text-align: center; border-radius: 50%; background: var(--bg-elevated); box-shadow: inset 0 0 40px rgba(255,255,255,.14); backdrop-filter: blur(25px); }
	.risk-orb span { font-size: clamp(4.2rem, 8vw, 7.5rem); font-weight: 750; line-height: .9; letter-spacing: -.07em; font-variant-numeric: tabular-nums; }.risk-orb small { font-size: 1.2rem; color: var(--text-secondary); }.risk-orb p { margin: 12px 0 0; color: var(--tone); font-size: .78rem; font-weight: 750; text-transform: uppercase; }
	.metrics { margin-bottom: 68px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }.metrics article { min-height: 130px; padding: 20px; display: flex; align-items: flex-start; gap: 14px; border-radius: var(--radius-md); }.metric-icon { min-width: 42px; height: 42px; display: grid; place-items: center; border-radius: 14px; color: var(--blue); background: color-mix(in srgb, var(--blue) 10%, transparent); }.metrics p,.metrics small { display: block; color: var(--text-secondary); }.metrics p { margin: 0 0 8px; font-size: .78rem; }.metrics strong { font-size: 1.12rem; }.metrics small { margin-top: 5px; font-size: .72rem; }
	.explanation { margin: -42px 0 24px; padding: clamp(22px, 4vw, 38px); display: grid; grid-template-columns: auto 1fr; gap: 18px; border-radius: var(--radius-lg); }.explanation-icon { width: 50px; height: 50px; display: grid; place-items: center; border-radius: 17px; color: var(--blue); background: color-mix(in srgb,var(--blue) 11%,transparent); }.explanation h2 { margin-bottom: 10px; font-size: clamp(1.4rem,2.5vw,2.2rem); letter-spacing: -.035em; }.explanation p { margin-bottom: 10px; max-width: 850px; color: var(--text-secondary); line-height: 1.65; }.explanation small { color: var(--text-tertiary); }
	.subpage-head h1 { margin: 0; font-size: clamp(2rem, 4vw, 3.4rem); letter-spacing: -.045em; }
	.forecast-strip { margin-bottom: 70px; padding: 18px 22px; display: grid; grid-template-columns: 1.6fr repeat(3, 1fr); align-items: center; gap: 12px; border-radius: var(--radius-lg); }.forecast-strip strong,.forecast-strip small { display: block; }.forecast-strip small { margin-top: 5px; color: var(--text-secondary); font-size: .75rem; }.day { padding: 10px 18px; border-left: 1px solid var(--border); }.day span { color: var(--text-secondary); font-size: .78rem; }.day strong { margin-top: 7px; font-size: 1.55rem; font-variant-numeric: tabular-nums; }
	.subpage-head { padding: 65px 8px 28px; display: flex; align-items: end; justify-content: space-between; gap: 20px; }.subpage-head p { margin: 10px 0 0; color: var(--text-secondary); }.subpage-head select,.history-form select,.history-form input { min-height: 48px; padding: 0 15px; border: 1px solid var(--border); border-radius: 15px; color: var(--text); background: var(--surface-solid); }
	.tracking-grid { display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(300px, .65fr); gap: 14px; }.tracking-map { height: 680px; overflow: hidden; border-radius: var(--radius-xl); }.detail { padding: 26px; border-radius: var(--radius-xl); }.detail-top { display: flex; justify-content: space-between; align-items: center; }.detail-top small { color: var(--text-secondary); }.badge { padding: 7px 10px; border-radius: var(--radius-pill); font-size: .72rem; font-weight: 750; text-transform: uppercase; }.badge.clear { color: var(--green); background: color-mix(in srgb,var(--green) 12%,transparent); }.badge.watch { color: var(--yellow); background: color-mix(in srgb,var(--yellow) 12%,transparent); }.badge.warning { color: var(--orange); background: color-mix(in srgb,var(--orange) 12%,transparent); }.badge.alert { color: var(--red); background: color-mix(in srgb,var(--red) 12%,transparent); }.detail h2 { margin: 34px 0 8px; font-size: 3.3rem; letter-spacing: -.055em; }.detail > p { color: var(--text-secondary); line-height: 1.55; }.detail dl { margin: 30px 0; }.detail dl div { padding: 15px 0; display: flex; justify-content: space-between; gap: 12px; border-top: 1px solid var(--border); }.detail dt { display: flex; align-items: center; gap: 8px; color: var(--text-secondary); }.detail dd { margin: 0; text-align: right; font-weight: 600; }.notice,.coverage-note { padding: 14px; display: flex; align-items: flex-start; gap: 10px; border-radius: 16px; color: var(--text-secondary); background: var(--surface-muted); }.notice p,.coverage-note p { margin: 0; font-size: .78rem; line-height: 1.5; }
	.horizon-picker { width: max-content; margin: 0 0 14px auto; padding: 5px; display: flex; gap: 4px; border-radius: var(--radius-pill); }.horizon-picker button { min-width: 58px; min-height: 42px; border: 0; border-radius: var(--radius-pill); color: var(--text-secondary); background: transparent; cursor: pointer; }.horizon-picker button.active { color: white; background: var(--blue); box-shadow: 0 8px 20px rgba(0,122,255,.2); }.horizon-picker button:disabled { opacity: .38; cursor: not-allowed; }
	.horizon-coming-soon { margin: 0 0 14px auto; display: flex; align-items: center; justify-content: flex-end; gap: 10px; opacity: .72; filter: grayscale(.7); }.horizon-coming-soon .horizon-picker { margin: 0; }.horizon-coming-soon > span { padding: 6px 9px; border: 1px solid var(--border); border-radius: var(--radius-pill); color: var(--text-secondary); background: var(--surface-muted); font-size: .7rem; font-weight: 750; text-transform: uppercase; letter-spacing: .04em; }
	.history-page { width: min(980px, 100%); margin: auto; }.history-form { padding: 18px; display: grid; grid-template-columns: 1fr 1fr auto; gap: 12px; align-items: end; border-radius: var(--radius-lg); }.history-form label span { margin: 0 0 8px 3px; display: block; color: var(--text-secondary); font-size: .76rem; font-weight: 600; }.history-form select,.history-form input { width: 100%; }.coverage-note { margin: 14px 0 30px; }.history-message { color: var(--text-secondary); text-align: center; }.history-result { margin: 12px 0; padding: 22px; display: flex; align-items: center; justify-content: space-between; border-radius: var(--radius-lg); }.history-result h2 { margin-bottom: 5px; }.history-result p { margin-bottom: 0; color: var(--text-secondary); }.historical-risk { text-align: right; }.historical-risk strong,.historical-risk span { display: block; }.historical-risk strong { font-size: 2.5rem; }.historical-risk span { color: var(--text-secondary); text-transform: capitalize; }
	.utility-page { width: min(980px,100%); margin: auto; }.offline-callout { margin-bottom: 18px; padding: 18px; display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 14px; border-radius: var(--radius-md); }.offline-callout > svg { color: var(--orange); }.offline-callout p { margin: 4px 0 0; color: var(--text-secondary); font-size: .82rem; }.offline-callout button { min-height: 44px; padding: 0 15px; border: 0; border-radius: var(--radius-pill); color: white; background: var(--blue); cursor: pointer; }.notification-list { display: grid; gap: 10px; }.notification { padding: 18px; display: flex; align-items: center; gap: 14px; border-radius: var(--radius-md); }.notification-mark { min-width: 42px; height: 42px; display: grid; place-items: center; border-radius: 14px; }.notification-mark.clear { color: var(--green); background: color-mix(in srgb,var(--green) 12%,transparent); }.notification-mark.watch { color: var(--yellow); background: color-mix(in srgb,var(--yellow) 12%,transparent); }.notification-mark.warning { color: var(--orange); background: color-mix(in srgb,var(--orange) 12%,transparent); }.notification-mark.alert { color: var(--red); background: color-mix(in srgb,var(--red) 12%,transparent); }.notification p,.notification small { margin: 4px 0 0; color: var(--text-secondary); font-size: .78rem; }.empty { padding: 60px 20px; border-radius: var(--radius-lg); color: var(--text-secondary); text-align: center; }.empty h2 { margin: 12px 0 6px; color: var(--text); }.settings-card,.legal { padding: 24px; border-radius: var(--radius-lg); }.settings-title { display: flex; gap: 14px; }.settings-title > span { min-width: 44px; height: 44px; display: grid; place-items: center; border-radius: 15px; color: var(--blue); background: color-mix(in srgb,var(--blue) 11%,transparent); }.settings-title h2 { margin: 0; }.settings-title p { margin: 6px 0 0; color: var(--text-secondary); }.settings-card form { margin-top: 24px; }.settings-card label { display: block; margin: 0 0 8px; color: var(--text-secondary); font-size: .78rem; font-weight: 600; }.phone-field { min-height: 50px; display: flex; align-items: center; gap: 8px; border: 1px solid var(--border); border-radius: 16px; background: var(--surface-solid); overflow: hidden; }.phone-field > span { padding-left: 14px; color: var(--text-secondary); }.phone-field input { min-width: 0; flex: 1; border: 0; outline: 0; color: var(--text); background: transparent; }.phone-field button { align-self: stretch; padding: 0 16px; display: flex; align-items: center; gap: 7px; border: 0; color: white; background: var(--blue); cursor: pointer; }.form-message { margin: 12px 0 0; color: var(--text-secondary); font-size: .8rem; }.linked { margin-top: 22px; padding: 14px; display: flex; align-items: center; gap: 10px; border-radius: 16px; background: var(--surface-muted); }.linked svg { color: var(--green); }.linked .danger { margin-left: auto; }.danger { border: 0; color: var(--red); background: transparent; cursor: pointer; }.legal { margin-top: 12px; display: grid; }.legal a,.danger-row { min-height: 54px; padding: 0 4px; display: flex; align-items: center; justify-content: space-between; border: 0; border-bottom: 1px solid var(--border); background: transparent; cursor: pointer; }.danger-row { justify-content: flex-start; gap: 9px; color: var(--red); border-bottom: 0; }
	.account-link,.account-switch{margin-top:20px}.account-switch{width:100%}
	footer { margin-top: 80px; padding: 24px 8px 8px; display: flex; align-items: center; justify-content: space-between; gap: 18px; border-top: 1px solid var(--border); color: var(--text-secondary); font-size: .76rem; }footer span { color: var(--text); font-weight: 750; }footer p { margin: 0; }
	@media (max-width: 900px) { .hero { grid-template-columns: 1fr; text-align: center; }.hero-copy { display: grid; justify-items: center; }.risk-orb { grid-row: 1; width: min(280px, 70vw); }.metrics { grid-template-columns: 1fr 1fr; }.tracking-grid { grid-template-columns: 1fr; }.tracking-map { height: 560px; }.forecast-strip { grid-template-columns: 1fr repeat(3,1fr); }.forecast-strip > div:first-child { grid-column: 1 / -1; }.history-form { grid-template-columns: 1fr 1fr; }.history-form button { grid-column: 1 / -1; } }
	@media (max-width: 620px) { .app-shell { width: min(100% - 18px, 1480px); padding-top: 9px; }.tabs { position: sticky; z-index: 10; top: 8px; width: 100%; justify-content: stretch; }.tabs button { flex: 1; justify-content: center; padding: 0 8px; }.hero { min-height: auto; padding: 48px 8px 40px; gap: 34px; }.hero h1 { font-size: clamp(2.65rem, 14vw, 4rem); }.hero-actions { width: 100%; }.hero-actions button { width: 100%; }.metrics { grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 52px; }.metrics article { min-height: 155px; padding: 16px; display: block; }.metric-icon { margin-bottom: 14px; }.section-heading { align-items: flex-start; }.section-heading button { display: none; }.map-frame { min-height: 590px; border-radius: 30px; }.map-insight { top: 12px; left: 12px; width: calc(100% - 24px); }.legend { bottom: 12px; left: 12px; width: calc(100% - 24px); justify-content: space-around; gap: 4px; }.forecast-strip { grid-template-columns: repeat(3,1fr); padding: 15px 8px; }.day { padding: 8px; text-align: center; }.day strong { font-size: 1.25rem; }.subpage-head { padding-top: 45px; align-items: flex-start; flex-direction: column; }.subpage-head select { width: 100%; }.tracking-map { height: 540px; }.history-form { grid-template-columns: 1fr; }.history-form button { grid-column: auto; }.history-result { align-items: flex-start; }.historical-risk strong { font-size: 2rem; } footer { align-items: flex-start; flex-direction: column; }footer p { display: none; } }
	@media (max-width: 620px) {
		.app-shell { padding-bottom: 84px; }
		.tabs { position: fixed; z-index: 30; top: auto; right: 8px; bottom: 8px; left: 8px; width: auto; margin: 0; padding-bottom: max(5px, env(safe-area-inset-bottom)); }
		.tabs button { min-width: 0; flex: 1; flex-direction: column; gap: 2px; padding: 5px 2px; font-size: .63rem; }
		.explanation { margin-top: -34px; grid-template-columns: 1fr; }
		.horizon-picker { width: 100%; overflow-x: auto; }.horizon-picker button { flex: 1; }
		.offline-callout { grid-template-columns: auto 1fr; }.offline-callout button { grid-column: 1 / -1; }
		.phone-field { align-items: stretch; flex-wrap: wrap; }.phone-field input { min-height: 48px; }.phone-field button { width: 100%; min-height: 48px; justify-content: center; }
	}
</style>
