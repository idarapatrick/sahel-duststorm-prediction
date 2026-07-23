<script lang="ts">
	import { onMount } from 'svelte';
	import { Activity, ArrowRight, Bell, CalendarDays, Clock3, Droplets, Gauge, Info, Map, Navigation, Phone, Settings, ShieldCheck, Sparkles, Thermometer, Trash2, Wind } from 'lucide-svelte';
	import AppHeader from '$lib/components/AppHeader.svelte';
	import OnboardingFlow from '$lib/components/OnboardingFlow.svelte';
	import { DEFAULT_LOCATION, locations as fallbackLocations } from '$lib/locations';
	import { ApiRequestError, confirmAccountDeletion, deleteFirebaseAccount, demoPrediction, getActiveAlerts, getAuthState, getCoveredLocations, getHistory, getLatestPrediction, getNotifications, getRecentHistory, logout, requestAccountDeletionOtp, saveAlertSubscription } from '$lib/api';
	import { finishFirebasePhoneVerification, signOutFirebase, startFirebasePhoneVerification } from '$lib/firebase';
	import type { ConfirmationResult } from 'firebase/auth';
	import type { ActiveAlert, AuthState, HistoricalSnapshot, Location, Prediction } from '$lib/types';

	let selected = DEFAULT_LOCATION;
	let locations: Location[] = fallbackLocations;
	let prediction: Prediction = demoPrediction(selected);
	let history: HistoricalSnapshot[] = [];
	let recentHistory: HistoricalSnapshot[] = [];
	let activeAlerts: ActiveAlert[] = [];
	let userNotifications: any[] = [];
	let alertThreshold: 'watch' | 'warning' | 'alert' = 'warning';
	let settingsBusy = false;
	let showDeleteConfirm = false;
	let deleteError = '';
	let deleteChallengeId = '';
	let deleteFirebaseConfirmation: ConfirmationResult | null = null;
	let deleteCode = '';
	let deleteStep: 'confirm' | 'otp' = 'confirm';
	let PredictionMapComponent: any = null;
	let linkedPhone = '';
	let phoneMessage = '';
	let phoneMessageType: 'success' | 'error' | 'info' = 'info';
	let authState: AuthState = { authenticated: false };
	let deviceId = '';
	let showSplash = true;
	let showOnboarding = false;
	let showAuth = false;
	let online = true;
	let locationRequest = 0;
	let fetchingPrediction = false;
	let loadingProgress = 0;
	let predictionLoadState: 'loading' | 'ready' | 'pending' | 'offline' = 'loading';
	let selectedDay: 'today' | 'tomorrow' | 'day-after' = 'today';
	let coverageLoading = true;
	let coverageError = '';
	let historyLoading = false;
	let historyMessage = '';
	let activeTab: 'overview' | 'tracking' | 'history' | 'notifications' | 'settings' = 'overview';
	let searchDate = new Date(Date.now() - 14 * 86400000).toISOString().slice(0, 10);
	const today = new Date().toISOString().slice(0, 10);
	const minDate = new Date(Date.now() - 89 * 86400000).toISOString().slice(0, 10);
	$: nextOutlookDate = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
	$: nextOutlook = prediction.outlooks?.find((item) => item.targetDate === nextOutlookDate);
	$: dayAfterDate = new Date(Date.now() + 2 * 86400000).toISOString().slice(0, 10);
	$: selectedTargetDate = selectedDay === 'today' ? today : selectedDay === 'tomorrow' ? nextOutlookDate : dayAfterDate;
	$: selectedOutlook = prediction.outlooks?.find((item) => item.targetDate === selectedTargetDate);
	$: activePrediction = selectedDay === 'today' ? prediction : selectedOutlook ? {
		...prediction,
		probability: selectedOutlook.probability,
		riskLevel: selectedOutlook.riskLevel,
		predictionDate: selectedOutlook.targetDate,
		conditions: selectedOutlook.conditions,
		surfaceData: selectedOutlook.surfaceData,
		environmentalEvidence: selectedOutlook.environmentalEvidence,
		inputQuality: undefined,
		evidenceSummary: selectedOutlook.inputCompleteness == null ? undefined : {
			inputCompleteness: selectedOutlook.inputCompleteness,
			observedFraction: selectedOutlook.observedFraction ?? 0,
			forecastFraction: selectedOutlook.forecastFraction ?? 0
		}
	} : demoPrediction(selected);
	$: probability = Math.round(activePrediction.probability * 100);
	$: riskCopy = activePrediction.available === false ? 'Prediction temporarily unavailable' : activePrediction.riskLevel === 'clear' ? 'No significant storm expected' : activePrediction.riskLevel === 'watch' ? 'Dust activity is possible' : activePrediction.riskLevel === 'warning' ? 'Dust storm conditions are likely' : 'Severe dust event expected';
	$: riskTone = activePrediction.riskLevel;
	$: conditions = activePrediction.conditions;
	$: aodEvidence = activePrediction.environmentalEvidence?.find((item) => item.variableName === 'previous_day_aod');
	$: soilEvidence = activePrediction.environmentalEvidence?.find((item) => item.variableName === 'soil_moisture');
	$: aodQuality = activePrediction.inputQuality?.fields?.previous_day_aod;
	$: aodAvailable = aodEvidence
		? aodEvidence.qualityStatus === 'valid' && aodEvidence.value != null
		: aodQuality?.available === true;
	$: aodSource = aodEvidence?.provider || aodQuality?.source;
	$: aodDescription = aodSource === 'modis'
		? 'Latest available satellite reading'
		: aodSource === 'cams-global'
			? 'Latest global atmospheric analysis'
			: 'Latest available particle reading';
	$: soilMoistureValue = conditions?.soilMoisture;
	$: aodValue = conditions?.aod;
	$: qualityFields = activePrediction.inputQuality?.fields;
	$: confirmedMissingReadings = activePrediction.environmentalEvidence?.length
		? [
			['soil_moisture', 'soil moisture'],
			['vegetation_water_content', 'vegetation water content'],
			['previous_day_aod', 'AOD particle reading']
		].filter(([key]) => activePrediction.environmentalEvidence?.some(
			(item) => item.variableName === key && ['missing', 'invalid', 'stale'].includes(item.qualityStatus)
		)).map(([, label]) => label)
		: qualityFields
			? [
				['soil_moisture', 'soil moisture'],
				['vegetation_water_content', 'vegetation water content'],
				['previous_day_aod', 'AOD particle reading']
			].filter(([key]) => qualityFields?.[key]?.available === false).map(([, label]) => label)
			: [];
	$: confirmedMissingMessage = confirmedMissingReadings.length === 1
		? `${confirmedMissingReadings[0]} is unavailable for this update.`
		: `${confirmedMissingReadings.slice(0, -1).join(', ')} and ${confirmedMissingReadings.at(-1)} are unavailable for this update.`;
	$: availableDayEvidence = activePrediction.environmentalEvidence?.filter(
		(item) => item.value != null && item.qualityStatus === 'valid'
	) ?? [];
	$: recordedEvidenceCount = availableDayEvidence.filter(
		(item) => ['observation', 'delayed_observation', 'analysis'].includes(item.kind)
	).length;
	$: forecastEvidenceCount = availableDayEvidence.filter((item) => item.kind === 'forecast').length;
	$: recordedEvidencePercent = availableDayEvidence.length
		? Math.round((recordedEvidenceCount / availableDayEvidence.length) * 100)
		: 0;
	$: forecastEvidencePercent = availableDayEvidence.length
		? Math.round((forecastEvidenceCount / availableDayEvidence.length) * 100)
		: 0;

	function windExplanation(speed: number | null | undefined) {
		if (speed == null) return 'No verified wind reading for this update';
		if (speed < 5) return 'The air is calm, with little movement of loose dust';
		if (speed < 15) return 'A light wind is moving through the area';
		if (speed < 25) return 'The wind is moving steadily and may disturb loose soil';
		if (speed < 35) return 'The wind is moving rapidly and can lift loose dust';
		return 'Strong winds can lift and carry large amounts of loose dust';
	}

	function temperatureExplanation(value: number | null | undefined) {
		if (value == null) return 'No verified temperature reading for this update';
		if (value < 20) return 'Conditions are relatively cool for this area';
		if (value < 30) return 'Conditions are warm';
		if (value < 40) return 'Conditions are hot and surface drying may increase';
		return 'Extreme heat can dry exposed ground quickly';
	}

	function soilMoistureExplanation(value: number | null | undefined) {
		if (value == null) return 'No verified soil-moisture reading for this update';
		if (value < 0.03) return 'The surface is extremely dry and loose dust can lift easily';
		if (value < 0.08) return 'The surface is very dry and may release loose dust';
		if (value < 0.15) return 'The surface is dry';
		if (value < 0.25) return 'The surface has moderate moisture';
		return 'The surface is moist, which can reduce loose dust';
	}

	function aodExplanation(value: number | null | undefined) {
		if (value == null) return 'No verified particle reading for this update';
		if (value < 0.05) return 'The sky has very few airborne particles and is likely clear';
		if (value < 0.20) return 'The sky has a low amount of airborne particles';
		if (value < 0.40) return 'The sky has a moderate amount of airborne particles';
		if (value < 0.70) return 'The sky has many airborne particles and may appear hazy';
		if (value < 1.00) return 'The particle level is high and visibility may be reduced';
		return 'The sky is very hazy with a very high amount of airborne particles';
	}

	async function loadLocation(location: Location) {
		const requestNumber = ++locationRequest;
		fetchingPrediction = true;
		loadingProgress = 8;
		predictionLoadState = 'loading';
		selectedDay = 'today';
		selected = location; history = []; historyMessage = '';
		localStorage.setItem('sahelwatch:location', JSON.stringify(location));
		prediction = demoPrediction(location);
		const progressTimer = window.setInterval(() => {
			if (requestNumber === locationRequest) loadingProgress = Math.min(92, loadingProgress + 3);
		}, 350);
		let central: { ok: true; value: Prediction } | { ok: false; error: unknown } = {
			ok: false, error: new Error('Prediction retrieval did not complete')
		};
		while (requestNumber === locationRequest) {
			central = await getLatestPrediction(location).then(
				(value) => ({ ok: true as const, value }),
				(error: unknown) => ({ ok: false as const, error })
			);
			if (central.ok && central.value.predictionDate === today) break;
			await new Promise((resolve) => window.setTimeout(resolve, 1200));
		}
		window.clearInterval(progressTimer);
		if (requestNumber !== locationRequest) return;
		const isCurrentDay = central.ok && central.value.predictionDate === today;
		if (central.ok && central.value.predictionDate === today) {
			prediction = central.value;
		} else if (central.ok) {
			const returnedOutlook = {
				targetDate: central.value.predictionDate,
				probability: central.value.probability,
				riskLevel: central.value.riskLevel,
				recordedAt: central.value.freshness?.recordedAt || new Date().toISOString()
			};
			prediction = {
				...demoPrediction(location),
				outlooks: central.value.outlooks?.length
					? central.value.outlooks
					: [returnedOutlook]
			};
		} else {
			prediction = demoPrediction(location);
		}
		predictionLoadState = isCurrentDay
			? 'ready'
			: central.ok
				? 'pending'
			: central.error instanceof ApiRequestError && central.error.status === 404
				? 'pending'
				: 'offline';
		online = central.ok;
		loadingProgress = 100;
		await new Promise((resolve) => window.setTimeout(resolve, 280));
		if (requestNumber !== locationRequest) return;
		fetchingPrediction = false;
		loadRecentHistory();
	}

	async function loadAlerts() {
		try { activeAlerts = await getActiveAlerts(); } catch { activeAlerts = []; }
		if (authState.authenticated) { try { userNotifications = await getNotifications(); } catch { userNotifications = []; } }
	}
	async function loadCoverage() {
		coverageLoading = true;
		coverageError = '';
		for (let attempt = 0; attempt < 3; attempt += 1) {
			try {
				const covered = await getCoveredLocations();
				if (!covered.length) throw new Error('No covered communities were returned.');
				locations = covered;
				localStorage.setItem('sahelwatch:covered_locations', JSON.stringify(covered));
				if (!covered.some((location) => location.name === selected.name && location.country === selected.country)) {
					selected = covered[0];
				}
				coverageLoading = false;
				return;
			} catch {
				if (attempt < 2) await new Promise((resolve) => window.setTimeout(resolve, 1000));
			}
		}
		coverageError = 'The location catalogue is still reconnecting.';
		coverageLoading = false;
		window.setTimeout(loadCoverage, 10_000);
	}
	async function refreshCentralPrediction() {
		try {
			const latest = await getLatestPrediction(selected);
			prediction = latest; predictionLoadState = 'ready'; online = true;
		} catch (error) {
			if (predictionLoadState !== 'ready') {
				predictionLoadState = error instanceof ApiRequestError && error.status === 404 ? 'pending' : 'offline';
			}
		}
		loadAlerts();
	}
	async function updateSubscription() {
		settingsBusy = true; phoneMessage = '';
		try { await saveAlertSubscription(selected, alertThreshold); phoneMessageType = 'success'; phoneMessage = `SMS alerts saved for ${selected.name} at ${alertThreshold} level.`; }
		catch (error) { phoneMessageType = 'error'; phoneMessage = error instanceof Error ? error.message : 'Could not save alert preference.'; }
		finally { settingsBusy = false; }
	}
	async function sendDeleteCode() {
		settingsBusy = true; deleteError = '';
		try {
			if (authState.user?.authProvider === 'firebase') deleteFirebaseConfirmation = await startFirebasePhoneVerification(`+${linkedPhone}`, 'delete-firebase-recaptcha');
			else { const result = await requestAccountDeletionOtp(deviceId); deleteChallengeId = result.challenge_id; }
			deleteStep = 'otp';
		}
		catch (error) { deleteError = error instanceof Error ? error.message : 'We could not send the verification code. Please try again.'; }
		finally { settingsBusy = false; }
	}
	async function removeAccount() {
		if (!/^\d{6}$/.test(deleteCode)) { deleteError = 'Enter the six-digit code sent to your phone.'; return; }
		settingsBusy = true; deleteError = '';
		try {
			if (authState.user?.authProvider === 'firebase') {
				const { idToken } = await finishFirebasePhoneVerification(deleteFirebaseConfirmation!, deleteCode);
				await deleteFirebaseAccount(idToken);
			} else await confirmAccountDeletion(deleteChallengeId, deleteCode);
			await signOutFirebase().catch(() => {});
			authState = { authenticated: false }; linkedPhone = ''; showDeleteConfirm = false; deleteStep = 'confirm'; deleteCode = ''; deleteChallengeId = ''; deleteFirebaseConfirmation = null; phoneMessageType = 'success'; phoneMessage = 'Account deletion confirmed. Your data will be permanently removed after seven days.';
		}
		catch (error) { deleteError = error instanceof Error ? error.message : 'We could not delete the account. Please try again.'; }
		finally { settingsBusy = false; }
	}
	function closeDeleteDialog() {
		if (settingsBusy) return;
		showDeleteConfirm = false; deleteStep = 'confirm'; deleteCode = ''; deleteChallengeId = ''; deleteFirebaseConfirmation = null; deleteError = '';
	}

	async function signOut() {
		await logout(); await signOutFirebase().catch(() => {}); authState = { authenticated: false }; linkedPhone = ''; phoneMessageType = 'info'; phoneMessage = 'You are logged out. SMS alerts are disabled on this device.';
	}
	function finishOnboarding(event: CustomEvent<{ location: Location; phoneUid?: string }>) {
		selected = event.detail.location; localStorage.setItem('sahelwatch:location', JSON.stringify(selected));
		localStorage.setItem('sahelwatch:onboarded', 'true'); showOnboarding = false; showAuth = false;
		if (event.detail.phoneUid) { linkedPhone = event.detail.phoneUid; getAuthState().then((state) => authState = state).catch(() => {}); }
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
		if (new URLSearchParams(window.location.search).get('tab') === 'settings') activeTab = 'settings';
		import('$lib/components/PredictionMap.svelte').then((module) => PredictionMapComponent = module.default);
		deviceId = localStorage.getItem('sahelwatch:device_id') || crypto.randomUUID(); localStorage.setItem('sahelwatch:device_id', deviceId);
		const cachedCoverage = localStorage.getItem('sahelwatch:covered_locations');
		if (cachedCoverage) {
			try {
				const parsed = JSON.parse(cachedCoverage);
				if (Array.isArray(parsed) && parsed.length > 1) locations = parsed;
			} catch { /* The live catalogue will replace an invalid cache. */ }
		}
		loadCoverage();
		const savedLocation = localStorage.getItem('sahelwatch:location');
		if (savedLocation) { try { selected = JSON.parse(savedLocation); } catch { /* use default */ } }
		const alreadyShown = sessionStorage.getItem('sahelwatch:splash_shown') === 'true';
		showSplash = !alreadyShown; sessionStorage.setItem('sahelwatch:splash_shown', 'true');
		window.setTimeout(() => { showSplash = false; showOnboarding = localStorage.getItem('sahelwatch:onboarded') !== 'true'; }, alreadyShown ? 0 : 1200);
		getAuthState().then((state) => { authState = state; linkedPhone = state.user?.phoneUid || ''; loadAlerts(); }).catch(() => {});
		loadLocation(selected); loadAlerts(); loadRecentHistory();
		// This only reads PostgreSQL. It never invokes the forecasting service.
		// A short interval lets an open dashboard adopt a newly stored hourly
		// revision without a reload or user-triggered inference.
		const reinforcementTimer = window.setInterval(() => {
			if (document.visibilityState === 'visible') refreshCentralPrediction();
		}, 15 * 1000);
		return () => window.clearInterval(reinforcementTimer);
	});
</script>

<svelte:head>
	<title>SahelWatch | Dust outlooks for the Sahel</title>
	<meta name="description" content="Dust and sand-storm outlooks for communities across the Sahel." />
</svelte:head>

{#if showSplash}
	<div class="splash" role="status" aria-label="Loading SahelWatch"><span><Wind size={34}/></span><strong>SahelWatch</strong><small>Preparing dust intelligence</small></div>
{:else if showOnboarding}
	<OnboardingFlow {deviceId} {locations} initialLocation={selected} {coverageLoading} {coverageError} on:retryCoverage={loadCoverage} on:complete={finishOnboarding}/>
{/if}
{#if showAuth}<OnboardingFlow {deviceId} {locations} initialLocation={selected} authOnly {coverageLoading} {coverageError} on:retryCoverage={loadCoverage} on:complete={finishOnboarding} on:close={() => showAuth=false}/>{/if}
{#if showDeleteConfirm}<div class="modal-scrim"><section class="confirm-card" role="alertdialog" aria-modal="true" aria-labelledby="delete-title" aria-describedby="delete-description"><span class="confirm-icon"><Trash2 size={22}/></span>{#if deleteStep === 'confirm'}<h2 id="delete-title">Delete your phone account?</h2><p id="delete-description">SMS alerts and sign-ins will stop immediately. Your phone account and alert choices will be permanently removed after seven days. We will send a code to +{linkedPhone} first.</p><div id="delete-firebase-recaptcha"></div>{:else}<h2 id="delete-title">Enter the code from your phone</h2><p id="delete-description">Enter the six-digit code sent to +{linkedPhone}. After verification, the account will be deactivated and scheduled for removal in seven days.</p><label for="delete-code">Verification code</label><input id="delete-code" class="delete-code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" bind:value={deleteCode} placeholder="000000" />{/if}{#if deleteError}<p class="delete-error" role="alert">{deleteError}</p>{/if}<div><button class="secondary" disabled={settingsBusy} on:click={closeDeleteDialog}>Keep account</button>{#if deleteStep === 'confirm'}<button class="delete-confirm" disabled={settingsBusy} on:click={sendDeleteCode}>{settingsBusy ? 'Sending code...' : 'Send code'}</button>{:else}<button class="delete-confirm" disabled={settingsBusy || deleteCode.length !== 6} on:click={removeAccount}>{settingsBusy ? 'Scheduling...' : 'Verify and schedule deletion'}</button>{/if}</div></section></div>{/if}

<div class="app-shell">
	{#if predictionLoadState === 'ready' && prediction.available !== false && probability >= 70}<div class="critical-banner" role="alert"><Bell size={18}/><strong>High dust risk for {selected.name}: {probability}%.</strong><button on:click={() => activeTab='tracking'}>View tracking</button></div>{/if}
	<AppHeader bind:selected {locations} {online} on:select={(e) => loadLocation(e.detail)} />

	<nav class="tabs glass" aria-label="Primary navigation">
		<button class:active={activeTab === 'overview'} on:click={() => activeTab = 'overview'}><Activity size={17}/>Overview</button>
		<button class:active={activeTab === 'tracking'} on:click={() => activeTab = 'tracking'}><Navigation size={17}/>Track</button>
		<button class:active={activeTab === 'history'} on:click={() => activeTab = 'history'}><CalendarDays size={17}/>History</button>
		<button class:active={activeTab === 'notifications'} on:click={() => { activeTab = 'notifications'; loadAlerts(); }}><Bell size={17}/>Alerts</button>
		<button class:active={activeTab === 'settings'} on:click={() => activeTab = 'settings'}><Settings size={17}/>Settings</button>
	</nav>

	<main id="main-content">
		{#if !fetchingPrediction && activeTab === 'overview'}
			<section class="day-tabs glass" aria-label="Choose an outlook day">
				<button class:active={selectedDay === 'today'} on:click={() => selectedDay = 'today'}><span>Today</span><small>{today}</small></button>
				<button class:active={selectedDay === 'tomorrow'} on:click={() => selectedDay = 'tomorrow'}><span>Tomorrow</span><small>{nextOutlookDate}</small></button>
				<button class:active={selectedDay === 'day-after'} on:click={() => selectedDay = 'day-after'}><span>Day after tomorrow</span><small>{dayAfterDate}</small></button>
			</section>
		{/if}
		{#if fetchingPrediction && activeTab === 'overview'}
			<section class="prediction-loading" role="status" aria-live="polite" aria-busy="true">
				<div class="loading-mark" aria-hidden="true"><Activity size={30}/></div>
				<p class="eyebrow">Latest central update</p>
				<h1>Fetching predictions for {selected.name}</h1>
				<p>SahelWatch is retrieving the latest stored outlook and environmental readings for this location.</p>
				<strong class="loading-percentage">{loadingProgress}%</strong>
				<div class="loading-track" role="progressbar" aria-label="Prediction retrieval progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow={loadingProgress}><span style={`width:${loadingProgress}%`}></span></div>
			</section>
		{:else if selectedDay === 'day-after' && activeTab === 'overview'}
			<section class="readiness-state glass" role="status">
				<p class="eyebrow">Extended outlook · {dayAfterDate}</p>
				<h1>Prediction readiness</h1>
				<strong>0%</strong>
				<div class="readiness-track"><span style="width:0%"></span></div>
				<p>SahelWatch is still checking this longer-range outlook. Available readings alone do not yet support a dependable result, so no risk percentage is shown.</p>
			</section>
		{:else if selectedDay === 'tomorrow' && !nextOutlook && activeTab === 'overview'}
			<section class="readiness-state glass" role="status">
				<p class="eyebrow">Tomorrow · {nextOutlookDate}</p>
				<h1>Collecting tomorrow’s central outlook</h1>
				<strong>0%</strong>
				<div class="readiness-track"><span style="width:0%"></span></div>
				<p>The worker has not stored a complete prediction and evidence record for tomorrow yet. This screen will update automatically.</p>
			</section>
		{:else if predictionLoadState === 'pending' && activeTab === 'overview'}
			<section class="prediction-state" role="status" aria-live="polite">
				<div class="loading-mark"><Clock3 size={30}/></div>
				<p class="eyebrow">Today’s central update</p>
				<h1>The outlook for {selected.name} is being prepared</h1>
				<p>The central service has not stored today’s result yet. SahelWatch will display it automatically when it arrives.</p>
			</section>
		{:else if predictionLoadState === 'offline' && activeTab === 'overview'}
			<section class="prediction-state" role="alert">
				<div class="loading-mark offline"><Info size={30}/></div>
				<p class="eyebrow">Connection delayed</p>
				<h1>Today’s outlook could not be retrieved</h1>
				<p>SahelWatch could not reach the central records for {selected.name}. It will try again automatically.</p>
			</section>
		{:else if activeTab === 'overview'}
			<section class="hero" aria-labelledby="forecast-heading">
				<div class="hero-copy">
					<div class="place"><i class:demo={!online}></i>{online ? 'Latest dust outlook' : 'Dust outlook unavailable'} · {selected.name}, {selected.country}</div>
					<p class="eyebrow">{selectedDay === 'today' ? 'Today’s dust outlook' : `Dust outlook for ${selectedTargetDate}`}</p>
					<h1 id="forecast-heading">{riskCopy}<span class="risk-word {riskTone}">{activePrediction.available === false ? 'Try again shortly' : `${probability}% risk`}</span></h1>
					<p class="summary">SahelWatch checks wind, heat, ground dryness and dust in the air to give communities early notice of possible dusty conditions.</p>
					<div class="hero-actions">
						<button class="primary" on:click={() => activeTab = 'tracking'}>Track this forecast <ArrowRight size={18}/></button>
						<button class="secondary" on:click={() => activeTab = 'history'}><CalendarDays size={18}/> Search past conditions</button>
					</div>
				</div>
				<div class="risk-orb {riskTone}" style={`--value:${activePrediction.available === false ? 0 : activePrediction.probability}`} aria-label={activePrediction.available === false ? 'Prediction unavailable' : `${probability} percent dust-storm probability`}>
					<div>
						{#if activePrediction.available === false}
							<span class="unavailable-value">!</span><p>Not available</p>
						{:else}
							<span>{probability}</span><small>%</small><p>{activePrediction.riskLevel}</p>
						{/if}
					</div>
				</div>
			</section>

			<section class="metrics" aria-label="Environmental forecast indicators">
				<article class="glass"><span class="metric-icon"><Wind size={20}/></span><div><p>Wind speed</p><strong>{conditions?.windSpeedKmh != null ? `${conditions.windSpeedKmh} km/h` : 'Unavailable'}</strong><small>{windExplanation(conditions?.windSpeedKmh)}{#if conditions?.windDirectionDeg != null}<span>{conditions.windDirectionDeg}° direction</span>{/if}</small></div></article>
				<article class="glass"><span class="metric-icon"><Thermometer size={20}/></span><div><p>Temperature</p><strong>{conditions?.temperatureC != null ? `${conditions.temperatureC}°C` : 'Unavailable'}</strong><small>{temperatureExplanation(conditions?.temperatureC)}</small></div></article>
				<article class="glass"><span class="metric-icon"><Droplets size={20}/></span><div><p>Soil moisture</p><strong>{soilMoistureValue != null ? `${(soilMoistureValue * 100).toFixed(1)}%` : 'Unavailable'}</strong><small>{soilMoistureExplanation(soilMoistureValue)}</small></div></article>
				<article class="glass"><span class="metric-icon"><Gauge size={20}/></span><div><p>Particles in the air (AOD)</p><strong>{aodAvailable && aodValue != null ? aodValue.toFixed(2) : 'Unavailable'}</strong><small>{aodAvailable ? aodExplanation(aodValue) : 'No verified AOD reading for this update'}{#if aodAvailable}<span>{aodDescription}</span>{/if}</small></div></article>
			</section>

			{#if confirmedMissingReadings.length > 0}<div class="data-warning" role="status"><Info size={18}/><p><strong>Confirmed missing reading:</strong> {confirmedMissingMessage} SahelWatch used the available readings and will check again during the next central update.</p></div>{/if}
			<section class="explanation glass">
				<span class="explanation-icon"><Sparkles size={22}/></span><div><p class="eyebrow">What this means</p><h2>Dust outlook for {selected.name} on {selectedTargetDate}</h2><p>This outlook updates automatically when newer environmental information becomes available.</p><small>{activePrediction.evidenceSummary ? `${Math.round(activePrediction.evidenceSummary.inputCompleteness * 100)}% of expected inputs were available. Of the available values, ${recordedEvidencePercent}% came from recorded or analysed conditions and ${forecastEvidencePercent}% came from forecasts.` : 'Weather details are shown only when verified source information is available.'}</small></div>
			</section>

		{:else if activeTab === 'tracking'}
			<section class="subpage-head"><div><p class="eyebrow">Tracking</p><h1>Monitor {selected.name}</h1><p>Inspect the current risk and predicted 24–48 hour window.</p></div><select bind:value={selected} on:change={() => loadLocation(selected)} aria-label="Tracking location">{#each locations as location}<option value={location}>{location.name}, {location.country}</option>{/each}</select></section>
			<section class="day-tabs glass tracking-days" aria-label="Choose a tracking day">
				<button class:active={selectedDay === 'today'} on:click={() => selectedDay = 'today'}><span>Today</span><small>{today}</small></button>
				<button class:active={selectedDay === 'tomorrow'} on:click={() => selectedDay = 'tomorrow'}><span>Tomorrow</span><small>{nextOutlookDate}</small></button>
				<button class:active={selectedDay === 'day-after'} on:click={() => selectedDay = 'day-after'}><span>Day after tomorrow</span><small>{dayAfterDate}</small></button>
			</section>
			{#if selectedDay === 'day-after' || (selectedDay === 'tomorrow' && !nextOutlook)}
				<section class="readiness-state glass" role="status"><p class="eyebrow">{selectedTargetDate}</p><h1>Tracking is not ready for this day</h1><strong>0%</strong><div class="readiness-track"><span style="width:0%"></span></div><p>SahelWatch displays tracking only after a complete central prediction and its supporting evidence have been stored.</p></section>
			{:else}
				<section class="tracking-grid">
					<div class="tracking-map glass">{#if PredictionMapComponent}<svelte:component this={PredictionMapComponent} location={selected} prediction={activePrediction} {conditions}/>{/if}</div>
					<aside class="detail glass"><div class="detail-top"><span class="badge {riskTone}">{activePrediction.riskLevel}</span><small>{selectedTargetDate}</small></div><h2>{probability}% chance</h2><p>{riskCopy}</p><dl><div><dt><Clock3 size={17}/>Evidence mixture</dt><dd>{activePrediction.evidenceSummary ? `${recordedEvidencePercent}% recorded or analysed · ${forecastEvidencePercent}% forecast` : 'Not available'}</dd></div><div><dt><Activity size={17}/>Wind speed</dt><dd>{conditions?.windSpeedKmh != null ? `${conditions.windSpeedKmh} km/h` : 'Not available'}</dd></div><div><dt><ShieldCheck size={17}/>Ground condition</dt><dd>{conditions?.soilMoisture != null ? `${(conditions.soilMoisture * 100).toFixed(1)}% moisture` : 'Not available'}</dd></div><div><dt><Map size={17}/>Area</dt><dd>{selected.name}, {selected.country}</dd></div></dl><div class="notice"><Info size={18}/><p>This tracking view combines the stored readings, analyses and forecasts shown above. It is not an evacuation route. Follow local authorities during dangerous weather.</p></div></aside>
				</section>
			{/if}

		{:else if activeTab === 'history'}
			<section class="history-page">
				<div class="subpage-head"><div><p class="eyebrow">90-day archive</p><h1>Look back with context</h1><p>Search prediction snapshots that SahelWatch actually recorded. Conditions are never reconstructed or invented.</p></div></div>
				{#if recentHistory.length}<div class="recent-history"><p class="eyebrow">Last 10 predictions for {selected.name}</p>{#each recentHistory as item}<article class="history-result glass"><div><strong>{new Date(item.recordedAt).toLocaleString()}</strong><p>Target {item.targetDate}</p></div><div class="historical-risk {item.riskLevel}"><strong>{Math.round(item.probability * 100)}%</strong><span>{item.riskLevel}</span></div></article>{/each}</div>{/if}
				<form class="history-form glass" on:submit|preventDefault={searchHistory}>
					<label><span>Covered location</span><select bind:value={selected}>{#each locations as location}<option value={location}>{location.name}, {location.country}</option>{/each}</select></label>
					<label><span>Date</span><input type="date" bind:value={searchDate} min={minDate} max={today}/></label>
					<button class="primary" disabled={historyLoading}>{historyLoading ? 'Searching…' : 'Search archive'} <ArrowRight size={18}/></button>
				</form>
				<div class="coverage-note"><Info size={18}/><p><strong>Coverage status:</strong> Operational and provisional communities use centrally monitored forecast cells. Provisional coverage means local performance evaluation is still continuing.</p></div>
				{#if historyMessage}<p class="history-message" role="status">{historyMessage}</p>{/if}
				{#each history as item}
					<article class="history-result glass"><div><p class="eyebrow">Recorded {new Date(item.recordedAt).toLocaleString()}</p><h2>{item.locationName}</h2><p>Prediction target: {item.targetDate}</p></div><div class="historical-risk {item.riskLevel}"><strong>{Math.round(item.probability * 100)}%</strong><span>{item.riskLevel}</span></div></article>
				{/each}
			</section>
		{:else if activeTab === 'notifications'}
			<section class="utility-page">
				<div class="subpage-head"><div><p class="eyebrow">Broadcast centre</p><h1>Notifications & alerts</h1><p>Risk changes and high-confidence storm broadcasts appear here and as in-app banners.</p></div></div>
				{#if !linkedPhone}<div class="offline-callout glass"><Phone size={22}/><div><strong>Offline alerts are not active</strong><p>Link a phone number in Settings to receive SMS broadcasts when you do not have internet access.</p></div><button on:click={() => activeTab = 'settings'}>Link phone</button></div>{/if}
				<div class="notification-list" aria-live="polite">
					{#each (authState.authenticated ? userNotifications.map((n) => ({ timestamp: n.created_at, probability: n.probability, alertLevel: n.current_level, locationName: n.location_name, confidence: n.direction })) : activeAlerts.flatMap((a) => a.updates.map((u) => ({ ...u, locationName: a.locationName })))).sort((a,b) => b.timestamp.localeCompare(a.timestamp)).slice(0, 20) as item}
						<article class="notification glass"><span class="notification-mark {item.alertLevel}"><Bell size={18}/></span><div><strong>{item.locationName}: {item.alertLevel}</strong><p>{Math.round(item.probability * 100)}% chance of dusty conditions · {typeof item.confidence === 'number' ? `${item.confidence}% of recent weather readings received` : item.confidence}</p><small>{new Date(item.timestamp).toLocaleString()}</small></div></article>
					{:else}<div class="empty glass"><Bell size={28}/><h2>No broadcasts yet</h2><p>New risk-level changes will be recorded here.</p></div>{/each}
				</div>
			</section>
		{:else}
			<section class="utility-page settings-page">
				<div class="subpage-head"><div><p class="eyebrow">Personalisation</p><h1>Settings</h1><p>Your phone number is the only personal information SahelWatch needs.</p></div></div>
				<section class="settings-card glass"><div class="settings-title"><span><Phone size={21}/></span><div><h2>Phone account & SMS alerts</h2><p>A verified international number is linked securely to your account. Phone linking is optional, but SMS alerts require it.</p></div></div>{#if linkedPhone}<div class="linked"><ShieldCheck size={18}/><span>+{linkedPhone}</span><button class="danger" on:click={signOut}>Log out</button></div><label class="threshold-field"><span>Alert threshold for {selected.name}</span><select bind:value={alertThreshold}><option value="watch">Watch and above</option><option value="warning">Warning and above</option><option value="alert">Alert only</option></select></label><button class="primary account-switch" disabled={settingsBusy} on:click={updateSubscription}>{settingsBusy ? 'Saving…' : 'Save SMS preference'}</button>{#if phoneMessage}<p class:error={phoneMessageType === 'error'} class="form-message" role={phoneMessageType === 'error' ? 'alert' : 'status'} aria-live="polite"><ShieldCheck size={17}/><span>{phoneMessage}</span></p>{/if}<button class="secondary account-switch" on:click={async () => { await signOut(); showAuth=true; }}>Log in with another number</button>{:else}<button class="primary account-link" on:click={() => showAuth=true}>Link phone or log in</button>{#if phoneMessage}<p class:error={phoneMessageType === 'error'} class="form-message" role={phoneMessageType === 'error' ? 'alert' : 'status'} aria-live="polite"><ShieldCheck size={17}/><span>{phoneMessage}</span></p>{/if}{/if}</section>
				<section class="legal glass"><a href="/privacy">Privacy policy <ArrowRight size={17}/></a><a href="/terms">Terms of use <ArrowRight size={17}/></a>{#if authState.authenticated}<button class="danger-row" disabled={settingsBusy} on:click={() => { deleteError=''; deleteStep='confirm'; showDeleteConfirm=true; }}><Trash2 size={17}/>Delete account and alert records</button>{/if}</section>
			</section>
		{/if}
	</main>
	<footer><span>SahelWatch</span><p>Low-cost environmental intelligence for the African Sahel.</p><small>Research forecast · Not an official emergency warning</small></footer>
</div>

<style>
	.modal-scrim{position:fixed;z-index:1200;inset:0;padding:20px;display:grid;place-items:center;background:rgba(0,0,0,.55);backdrop-filter:blur(12px)}.confirm-card{width:min(440px,100%);padding:28px;border:1px solid var(--border);border-radius:28px;color:var(--text);background:var(--surface-solid);box-shadow:var(--shadow-lg)}.confirm-icon{width:48px;height:48px;display:grid;place-items:center;border-radius:16px;color:var(--red);background:color-mix(in srgb,var(--red) 12%,transparent)}.confirm-card h2{margin:18px 0 10px}.confirm-card p{color:var(--text-secondary);line-height:1.6}.confirm-card .delete-error{padding:10px 12px;border-radius:12px;color:var(--red);background:color-mix(in srgb,var(--red) 10%,transparent)}.confirm-card>div{margin-top:24px;display:grid;grid-template-columns:1fr 1fr;gap:10px}.confirm-card button{min-height:48px;border:0;border-radius:15px;font-weight:700;cursor:pointer}.delete-confirm{color:white;background:var(--red)}
	.critical-banner{position:sticky;z-index:40;top:8px;margin-bottom:8px;padding:12px 16px;display:flex;align-items:center;gap:10px;border-radius:16px;color:white;background:var(--red);box-shadow:var(--shadow-md)}.critical-banner button{margin-left:auto;min-height:44px;padding:0 14px;border:1px solid rgba(255,255,255,.45);border-radius:14px;color:white;background:rgba(255,255,255,.12);cursor:pointer}.threshold-field{margin-top:20px;display:grid;gap:8px;color:var(--text-secondary);font-size:.8rem;font-weight:600}.threshold-field select{min-height:48px;padding:0 14px;border:1px solid var(--border);border-radius:14px;color:var(--text);background:var(--surface-solid)}.map-loading{height:100%;display:grid;place-items:center;color:var(--text-secondary)}
	.splash{position:fixed;z-index:1100;inset:0;display:grid;place-content:center;justify-items:center;background:var(--bg);color:var(--text)}.splash span{width:74px;height:74px;display:grid;place-items:center;border-radius:24px;color:white;background:var(--blue);box-shadow:0 22px 50px rgba(0,122,255,.25)}.splash strong{margin-top:18px;font-size:1.55rem;letter-spacing:-.04em}.splash small{margin-top:6px;color:var(--text-secondary)}
	.app-shell { width: min(1480px, calc(100% - 28px)); margin: 0 auto; padding: 14px 0 28px; }
	.tabs { width: max-content; margin: 16px auto 0; padding: 5px; display: flex; gap: 3px; border-radius: var(--radius-pill); }
	.tabs button { min-height: 42px; padding: 0 16px; display: flex; align-items: center; gap: 7px; border: 0; border-radius: var(--radius-pill); color: var(--text-secondary); background: transparent; cursor: pointer; transition: var(--ease); }
	.tabs button.active { color: var(--text); background: var(--surface-solid); box-shadow: var(--shadow-sm); }
	main { min-height: 70dvh; }
	.prediction-loading { min-height: 68dvh; padding: 70px 24px; display: grid; place-content: center; justify-items: center; text-align: center; }
	.prediction-state { min-height: 68dvh; padding: 70px 24px; display: grid; place-content: center; justify-items: center; text-align: center; }
	.prediction-state .loading-mark { width: 66px; height: 66px; margin-bottom: 24px; display:grid; place-items:center; border-radius:22px; color:var(--blue); background:color-mix(in srgb,var(--blue) 11%,var(--surface)); }
	.prediction-state .loading-mark.offline { color:var(--orange); background:color-mix(in srgb,var(--orange) 10%,var(--surface)); }
	.prediction-state h1 { max-width:780px; margin:0; font-size:clamp(2.2rem,6vw,4.8rem); line-height:1; letter-spacing:-.055em; }
	.prediction-state > p:not(.eyebrow) { max-width:640px; margin:18px 0 0; color:var(--text-secondary); line-height:1.65; }
	.prediction-loading .loading-mark { width: 66px; height: 66px; margin-bottom: 24px; display: grid; place-items: center; border-radius: 22px; color: var(--blue); background: color-mix(in srgb, var(--blue) 11%, var(--surface)); animation: loading-pulse 1.4s ease-in-out infinite; }
	.prediction-loading h1 { max-width: 760px; margin: 0; font-size: clamp(2.2rem, 6vw, 4.8rem); line-height: 1; letter-spacing: -.055em; }
	.prediction-loading > p:not(.eyebrow) { max-width: 620px; margin: 18px 0 28px; color: var(--text-secondary); font-size: 1rem; line-height: 1.65; }
	.loading-percentage { margin-bottom: 12px; color: var(--blue); font-size: 1.6rem; font-variant-numeric: tabular-nums; }
	.loading-track { width: min(440px, 78vw); height: 7px; overflow: hidden; border-radius: var(--radius-pill); background: color-mix(in srgb, var(--blue) 10%, var(--surface-muted)); }
	.loading-track span { height: 100%; display: block; border-radius: inherit; background: var(--blue); transition: width .3s ease-out; }
	@keyframes loading-pulse { 50% { transform: scale(1.06); opacity: .72; } }
	.day-tabs { margin: 34px 0 0; padding: 7px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 7px; border-radius: var(--radius-lg); }
	.day-tabs button { min-height: 70px; padding: 10px 14px; display: grid; align-content: center; justify-items: start; border: 1px solid transparent; border-radius: 17px; color: var(--text-secondary); background: transparent; cursor: pointer; }
	.day-tabs button.active { border-color: color-mix(in srgb,var(--blue) 35%,var(--border)); color: var(--text); background: color-mix(in srgb,var(--blue) 9%,var(--surface)); box-shadow: var(--shadow-sm); }
	.day-tabs span,.day-tabs small { display:block; }.day-tabs span { font-weight:750; }.day-tabs small { margin-top:4px; color:var(--text-tertiary); font-size:.72rem; }
	.tracking-days { margin: 0 0 16px; }
	.readiness-state { min-height: 440px; margin-top: 18px; padding: 48px 24px; display: grid; place-content: center; justify-items: center; border-radius: var(--radius-xl); text-align:center; }
	.readiness-state h1 { margin: 0; font-size: clamp(2rem,5vw,4rem); letter-spacing:-.05em; }.readiness-state > strong { margin:20px 0 10px; color:var(--blue); font-size:2.3rem; font-variant-numeric:tabular-nums; }.readiness-state > p:not(.eyebrow) { max-width:680px; margin:20px 0 0; color:var(--text-secondary); line-height:1.65; }
	.readiness-track { width:min(460px,78vw); height:8px; overflow:hidden; border-radius:var(--radius-pill); background:var(--surface-muted); }.readiness-track span { height:100%; display:block; background:var(--blue); }
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
	.risk-orb span.unavailable-value { font-size: clamp(3.5rem, 7vw, 6rem); letter-spacing: 0; }
	.metrics { margin-bottom: 68px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }.metrics article { min-height: 130px; padding: 20px; display: flex; align-items: flex-start; gap: 14px; border-radius: var(--radius-md); }.metric-icon { min-width: 42px; height: 42px; display: grid; place-items: center; border-radius: 14px; color: var(--blue); background: color-mix(in srgb, var(--blue) 10%, transparent); }.metrics p,.metrics small { display: block; color: var(--text-secondary); }.metrics p { margin: 0 0 8px; font-size: .78rem; }.metrics strong { font-size: 1.12rem; }.metrics small { margin-top: 5px; font-size: .72rem; }
	.explanation { margin: -42px 0 24px; padding: clamp(22px, 4vw, 38px); display: grid; grid-template-columns: auto 1fr; gap: 18px; border-radius: var(--radius-lg); }.explanation-icon { width: 50px; height: 50px; display: grid; place-items: center; border-radius: 17px; color: var(--blue); background: color-mix(in srgb,var(--blue) 11%,transparent); }.explanation h2 { margin-bottom: 10px; font-size: clamp(1.4rem,2.5vw,2.2rem); letter-spacing: -.035em; }.explanation p { margin-bottom: 10px; max-width: 850px; color: var(--text-secondary); line-height: 1.65; }.explanation small { color: var(--text-tertiary); }
	.data-warning{margin:-42px 0 56px;padding:14px 16px;display:flex;align-items:flex-start;gap:10px;border:1px solid color-mix(in srgb,var(--orange) 35%,var(--border));border-radius:16px;color:var(--text-secondary);background:color-mix(in srgb,var(--orange) 8%,var(--surface))}.data-warning p{margin:0;font-size:.8rem;line-height:1.5}.data-warning svg{flex:none;color:var(--orange)}
	.subpage-head h1 { margin: 0; font-size: clamp(2rem, 4vw, 3.4rem); letter-spacing: -.045em; }
	.forecast-strip { margin-bottom: 70px; padding: 18px 22px; display: grid; grid-template-columns: 1.6fr repeat(3, 1fr); align-items: center; gap: 12px; border-radius: var(--radius-lg); }.forecast-strip strong,.forecast-strip small { display: block; }.forecast-strip small { margin-top: 5px; color: var(--text-secondary); font-size: .75rem; }.day { padding: 10px 18px; border-left: 1px solid var(--border); }.day span { color: var(--text-secondary); font-size: .78rem; }.day strong { margin-top: 7px; font-size: 1.55rem; font-variant-numeric: tabular-nums; }
	.subpage-head { padding: 65px 8px 28px; display: flex; align-items: end; justify-content: space-between; gap: 20px; }.subpage-head p { margin: 10px 0 0; color: var(--text-secondary); }.subpage-head select,.history-form select,.history-form input { min-height: 48px; padding: 0 15px; border: 1px solid var(--border); border-radius: 15px; color: var(--text); background: var(--surface-solid); }
	.tracking-grid { display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(300px, .65fr); gap: 14px; }.tracking-map { height: 680px; overflow: hidden; border-radius: var(--radius-xl); }.detail { padding: 26px; border-radius: var(--radius-xl); }.detail-top { display: flex; justify-content: space-between; align-items: center; }.detail-top small { color: var(--text-secondary); }.badge { padding: 7px 10px; border-radius: var(--radius-pill); font-size: .72rem; font-weight: 750; text-transform: uppercase; }.badge.clear { color: var(--green); background: color-mix(in srgb,var(--green) 12%,transparent); }.badge.watch { color: var(--yellow); background: color-mix(in srgb,var(--yellow) 12%,transparent); }.badge.warning { color: var(--orange); background: color-mix(in srgb,var(--orange) 12%,transparent); }.badge.alert { color: var(--red); background: color-mix(in srgb,var(--red) 12%,transparent); }.detail h2 { margin: 34px 0 8px; font-size: 3.3rem; letter-spacing: -.055em; }.detail > p { color: var(--text-secondary); line-height: 1.55; }.detail dl { margin: 30px 0; }.detail dl div { padding: 15px 0; display: flex; justify-content: space-between; gap: 12px; border-top: 1px solid var(--border); }.detail dt { display: flex; align-items: center; gap: 8px; color: var(--text-secondary); }.detail dd { margin: 0; text-align: right; font-weight: 600; }.notice,.coverage-note { padding: 14px; display: flex; align-items: flex-start; gap: 10px; border-radius: 16px; color: var(--text-secondary); background: var(--surface-muted); }.notice p,.coverage-note p { margin: 0; font-size: .78rem; line-height: 1.5; }
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
		.day-tabs { grid-template-columns: 1fr; }.day-tabs button { min-height:58px; }
		.offline-callout { grid-template-columns: auto 1fr; }.offline-callout button { grid-column: 1 / -1; }
		.phone-field { align-items: stretch; flex-wrap: wrap; }.phone-field input { min-height: 48px; }.phone-field button { width: 100%; min-height: 48px; justify-content: center; }
	}
	.confirm-card label{display:block;margin:18px 0 8px;font-size:.8rem;font-weight:700}.delete-code{width:100%;min-height:52px;padding:0 14px;border:1px solid var(--border);border-radius:15px;color:var(--text);background:var(--surface-muted);font-size:1.35rem;letter-spacing:.25em;text-align:center}
	.form-message{padding:12px 14px;display:flex;align-items:center;gap:9px;border:1px solid color-mix(in srgb,var(--green) 30%,var(--border));border-radius:14px;color:var(--text);background:color-mix(in srgb,var(--green) 10%,var(--surface));font-size:.82rem}.form-message svg{flex:none;color:var(--green)}
	.form-message.error{border-color:color-mix(in srgb,var(--red) 35%,var(--border));background:color-mix(in srgb,var(--red) 10%,var(--surface))}.form-message.error svg{color:var(--red)}
	.metrics small span{display:block;margin-top:4px;color:var(--text-tertiary)}
	@media (prefers-reduced-motion: reduce) {
		.loading-mark { animation: none; }
	}
</style>
