<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { ArrowLeft, ArrowRight, Check, LocateFixed, MessageSquare, Phone, Search, ShieldCheck, X } from 'lucide-svelte';
	import { createFirebaseSession, getNearestCoveredLocation, requestOtp, verifyOtp } from '$lib/api';
	import { firebaseAuthEnabled, finishFirebasePhoneVerification, legacyPhoneAuthEnabled, startFirebasePhoneVerification } from '$lib/firebase';
	import type { ConfirmationResult } from 'firebase/auth';
	import { DEFAULT_LOCATION, SAHEL_BOUNDS } from '$lib/locations';
	import type { Location } from '$lib/types';

	export let deviceId: string;
	export let locations: Location[] = [DEFAULT_LOCATION];
	export let initialLocation: Location = locations[0] || DEFAULT_LOCATION;
	export let authOnly = false;
	export let coverageLoading = false;
	export let coverageError = '';
	const dispatch = createEventDispatcher<{ complete: { location: Location; phoneUid?: string }; close: void; retryCoverage: void }>();
	let step: 'location' | 'phone-choice' | 'phone' | 'otp' = authOnly ? 'phone-choice' : 'location';
	let selected = initialLocation;
	let purpose: 'signup' | 'login' = 'signup';
	let phone = '';
	let code = '';
	let challengeId = '';
	let firebaseConfirmation: ConfirmationResult | null = null;
	let busy = false;
	let message = '';
	let locationQuery = '';
	$: phoneValid = /^\+[1-9][0-9]{9,14}$/.test(phone.trim());
	$: filteredLocations = locations.filter((location) =>
		`${location.name} ${location.country}`.toLowerCase().includes(locationQuery.trim().toLowerCase())
	);
	$: if (!locations.some((location) => location.name === selected.name && location.country === selected.country) && locations.length) {
		selected = locations[0];
	}

	function chooseLocation() { step = 'phone-choice'; message = ''; }
	function finish(phoneUid?: string) { dispatch('complete', { location: selected, phoneUid }); }

	function useMyLocation() {
		message = '';
		if (!navigator.geolocation) { message = 'Location access is not available in this browser. Pick a monitored community instead.'; return; }
		busy = true;
		navigator.geolocation.getCurrentPosition(async ({ coords }) => {
			const { latitude: lat, longitude: lon } = coords;
			if (lat < SAHEL_BOUNDS.latMin || lat > SAHEL_BOUNDS.latMax || lon < SAHEL_BOUNDS.lonMin || lon > SAHEL_BOUNDS.lonMax) {
				busy = false; message = 'Your current position is outside the forecast region. Please pick a covered community.'; return;
			}
			try { selected = await getNearestCoveredLocation(lat, lon); message = `${selected.name} is the nearest monitored community.`; }
			catch { selected = locations.reduce((best, item) => Math.hypot(item.lat-lat,item.lon-lon) < Math.hypot(best.lat-lat,best.lon-lon) ? item : best); message = `${selected.name} is the nearest available community.`; }
			finally { busy = false; }
		}, () => { busy = false; message = 'Location permission was not granted. Pick a monitored community instead.'; }, { enableHighAccuracy: false, timeout: 10000 });
	}

	async function sendCode() {
		if (!phoneValid) { message = 'Use international format starting with +, for example +2348012345678.'; return; }
		busy = true; message = '';
		try {
			if (firebaseAuthEnabled()) firebaseConfirmation = await startFirebasePhoneVerification(phone, 'firebase-recaptcha');
			else if (legacyPhoneAuthEnabled()) { const result = await requestOtp(phone, purpose, deviceId); challengeId = result.challenge_id; }
			else throw new Error('Phone verification is not ready on this deployment. The Firebase web settings must be added in Vercel, then the frontend must be redeployed.');
			step = 'otp';
		} catch (error) { message = error instanceof Error ? error.message : 'Could not send the verification code.'; }
		finally { busy = false; }
	}

	async function confirmCode() {
		busy = true; message = '';
		try {
			const result = firebaseAuthEnabled()
				? await finishFirebasePhoneVerification(firebaseConfirmation!, code).then(({ idToken }) => createFirebaseSession(idToken, purpose, deviceId, purpose === 'signup' ? selected : undefined))
				: legacyPhoneAuthEnabled()
					? await verifyOtp(challengeId, code, purpose === 'signup' ? selected : undefined)
					: (() => { throw new Error('Phone verification is not configured for this deployment.'); })();
			finish(result.phone_uid);
		} catch (error) { message = error instanceof Error ? error.message : 'Could not verify this code.'; }
		finally { busy = false; }
	}
</script>

<div class="veil" role="presentation">
	<section class="sheet" role="dialog" aria-modal="true" aria-labelledby="onboarding-title">
		{#if authOnly}<button class="close" aria-label="Close" on:click={() => dispatch('close')}><X size={20}/></button>{/if}
		<div class="brand"><span><ShieldCheck size={21}/></span> SahelWatch</div>
		{#if step === 'location'}
			<p class="step">Step 1 of 2</p><h1 id="onboarding-title">Choose your forecast location</h1>
			<p class="intro">Choose a monitored city, town or rural community. Provisional areas are available while local performance checks continue.</p>
			<button class="locate" disabled={busy} on:click={useMyLocation}><LocateFixed size={19}/>{busy ? 'Checking location…' : 'Use my current location'}</button>
			<label for="covered-location-search">Monitored communities</label>
			{#if coverageLoading}
				<div class="coverage-state" role="status"><span class="spinner"></span><div><strong>Loading covered communities</strong><small>SahelWatch is retrieving the current location catalogue.</small></div></div>
			{:else if coverageError}
				<div class="coverage-state error" role="alert"><div><strong>Locations could not be loaded</strong><small>{coverageError}</small><button type="button" on:click={() => dispatch('retryCoverage')}>Try again</button></div></div>
			{:else}
				<div class="location-picker">
					<div class="location-search"><Search size={18}/><input id="covered-location-search" bind:value={locationQuery} placeholder="Search a city, town or village" autocomplete="off"/></div>
					<div class="location-list" role="listbox" aria-label="Covered communities">
						{#each filteredLocations as location}
							<button type="button" class:selected={selected.name === location.name && selected.country === location.country} role="option" aria-selected={selected.name === location.name && selected.country === location.country} on:click={() => selected = location}>
								<span><strong>{location.name}</strong><small>{location.country}{location.placeType ? ` · ${location.placeType}` : ''}</small></span>
								{#if selected.name === location.name && selected.country === location.country}<Check size={18}/>{/if}
							</button>
						{:else}
							<p>No covered community matches “{locationQuery}”.</p>
						{/each}
					</div>
				</div>
			{/if}
			{#if message}<p class="message" role="status">{message}</p>{/if}
			<button class="primary" disabled={coverageLoading || Boolean(coverageError) || !locations.length} on:click={chooseLocation}>Continue with {selected.name}<ArrowRight size={18}/></button>
		{:else if step === 'phone-choice'}
			<p class="step">{authOnly ? 'Account' : 'Step 2 of 2 · Optional'}</p><h1 id="onboarding-title">Receive alerts beyond the app</h1>
			<p class="intro">Link a phone number to receive high-risk dust alerts by SMS. You can use all in-app forecasts without linking a number.</p>
			<div class="benefit"><MessageSquare size={21}/><div><strong>SMS alerts require a verified number</strong><p>Without one, alerts are available only while you can access SahelWatch online.</p></div></div>
			<button class="primary" on:click={() => { purpose='signup'; step='phone'; }}>Create account with phone<Phone size={18}/></button>
			<button class="secondary" on:click={() => { purpose='login'; step='phone'; }}>Log in with an existing number</button>
			{#if !authOnly}<button class="text" on:click={() => finish()}>Continue without SMS alerts</button>{/if}
		{:else if step === 'phone'}
			<button class="back" aria-label="Back" on:click={() => { step='phone-choice'; message=''; }}><ArrowLeft size={19}/></button>
			<p class="step">{purpose === 'signup' ? 'Create phone account' : 'Secure login'}</p><h1 id="onboarding-title">Enter your phone number</h1>
			<p class="intro">Use international E.164 format beginning with +. Your number is verified securely before it is linked to SahelWatch.</p>
			<label for="phone">International phone number</label><input id="phone" type="tel" autocomplete="tel" bind:value={phone} placeholder="+2348012345678" aria-describedby="phone-help" on:blur={() => { if (phone && !phoneValid) message='Use international format starting with +, for example +2348012345678.'; }} /><small id="phone-help" class="helper">Include +, country code and subscriber number. Do not start with a local 0.</small>
			<div id="firebase-recaptcha"></div>
			{#if message}<p class="message error" role="alert">{message}</p>{/if}
			<button class="primary" disabled={busy || !phoneValid} on:click={sendCode}>{busy ? 'Sending code…' : 'Send verification code'}<ArrowRight size={18}/></button>
		{:else}
			<button class="back" aria-label="Back" on:click={() => { step='phone'; code=''; message=''; }}><ArrowLeft size={19}/></button>
			<p class="step">Verification</p><h1 id="onboarding-title">Check your messages</h1>
			<p class="intro">Enter the six-digit code sent to {phone}. It expires after 10 minutes.</p>
			<label for="otp">Verification code</label><input id="otp" class="otp" inputmode="numeric" autocomplete="one-time-code" maxlength="6" bind:value={code} placeholder="000000" />
			{#if message}<p class="message error" role="alert">{message}</p>{/if}
			<button class="primary" disabled={busy || code.length !== 6} on:click={confirmCode}>{busy ? 'Verifying…' : 'Verify and continue'}<Check size={18}/></button>
		{/if}
		<p class="privacy">By continuing, you agree to the Terms and acknowledge the <a href="/privacy">Privacy Policy</a>.</p>
	</section>
</div>

<style>
	.veil{position:fixed;z-index:1000;inset:0;display:grid;place-items:center;padding:20px;background:color-mix(in srgb,var(--bg) 72%,transparent);backdrop-filter:blur(24px)}
	.sheet{position:relative;width:min(520px,100%);max-height:calc(100dvh - 32px);overflow:auto;padding:clamp(26px,5vw,46px);border:1px solid var(--border);border-radius:36px;background:var(--bg-elevated);box-shadow:0 30px 100px rgba(0,0,0,.2)}
	.brand{display:flex;align-items:center;gap:9px;font-weight:760}.brand span{width:38px;height:38px;display:grid;place-items:center;border-radius:13px;color:white;background:var(--blue)}
	.step{margin:38px 0 8px;color:var(--blue);font-size:.72rem;font-weight:750;text-transform:uppercase;letter-spacing:.08em}h1{margin:0;font-size:clamp(2rem,7vw,3.1rem);line-height:1.02;letter-spacing:-.055em}.intro{margin:16px 0 26px;color:var(--text-secondary);line-height:1.6}
	label{display:block;margin:20px 0 8px;font-size:.78rem;font-weight:700}input{width:100%;min-height:52px;padding:0 15px;border:1px solid var(--border);border-radius:16px;color:var(--text);background:var(--surface-solid);font-size:1rem}.otp{font-size:1.5rem;letter-spacing:.3em;text-align:center;font-variant-numeric:tabular-nums}
	.helper{display:block;margin:7px 3px 0;color:var(--text-tertiary);font-size:.72rem;line-height:1.45}
	.coverage-state{min-height:82px;padding:16px;display:flex;align-items:center;gap:12px;border:1px solid var(--border);border-radius:16px;background:var(--surface-muted)}.coverage-state strong,.coverage-state small{display:block}.coverage-state small{margin-top:4px;color:var(--text-secondary);line-height:1.4}.coverage-state.error{border-color:color-mix(in srgb,var(--red) 35%,var(--border))}.coverage-state.error button{min-height:40px;margin-top:10px;padding:0 14px;color:white;background:var(--blue)}.spinner{width:22px;height:22px;flex:none;border:3px solid var(--border);border-top-color:var(--blue);border-radius:50%;animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
	.location-picker{border:1px solid var(--border);border-radius:18px;background:var(--surface-solid);overflow:hidden}.location-search{height:52px;padding:0 14px;display:flex;align-items:center;gap:9px;border-bottom:1px solid var(--border);color:var(--text-tertiary)}.location-search input{min-height:0;padding:0;border:0;border-radius:0;outline:0;background:transparent}.location-list{max-height:min(280px,35vh);padding:7px;overflow-y:auto;overscroll-behavior:contain}.location-list button{width:100%;min-height:54px;padding:8px 10px;display:flex;align-items:center;justify-content:space-between;text-align:left;background:transparent}.location-list button.selected{color:var(--blue);background:color-mix(in srgb,var(--blue) 10%,transparent)}.location-list strong,.location-list small{display:block}.location-list small{margin-top:3px;color:var(--text-secondary);font-size:.72rem}.location-list p{padding:14px;color:var(--text-secondary);font-size:.82rem}
	button{min-height:48px;border:0;border-radius:16px;font:inherit;font-weight:700;cursor:pointer}button:disabled{opacity:.45;cursor:not-allowed}.primary,.secondary,.locate,.text{width:100%;margin-top:12px}.primary{display:flex;align-items:center;justify-content:center;gap:8px;color:white;background:var(--blue)}.secondary,.locate{display:flex;align-items:center;justify-content:center;gap:8px;color:var(--text);background:var(--surface-muted)}.locate{margin-bottom:18px}.text{color:var(--text-secondary);background:transparent}.back,.close{position:absolute;top:24px;width:44px;background:var(--surface-muted)}.back{right:24px}.close{right:24px}.benefit{padding:16px;display:flex;gap:12px;border-radius:18px;background:var(--surface-muted)}.benefit p{margin:5px 0 0;color:var(--text-secondary);font-size:.8rem;line-height:1.45}.message{margin:12px 0 0;color:var(--text-secondary);font-size:.82rem}.error{color:var(--red)}.privacy{margin:24px 0 0;color:var(--text-tertiary);font-size:.72rem;line-height:1.5}.privacy a{color:var(--blue)}
	@media(prefers-reduced-motion:no-preference){.sheet{animation:enter .25s ease-out}@keyframes enter{from{opacity:0;transform:translateY(14px) scale(.98)}}}
</style>
