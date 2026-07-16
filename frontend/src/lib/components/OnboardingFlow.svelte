<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { ArrowLeft, ArrowRight, Check, LocateFixed, MessageSquare, Phone, ShieldCheck, X } from 'lucide-svelte';
	import { requestOtp, verifyOtp } from '$lib/api';
	import { locations, SAHEL_BOUNDS } from '$lib/locations';
	import type { Location } from '$lib/types';

	export let deviceId: string;
	export let initialLocation: Location = locations[0];
	export let authOnly = false;
	const dispatch = createEventDispatcher<{ complete: { location: Location; phoneUid?: string }; close: void }>();
	let step: 'location' | 'phone-choice' | 'phone' | 'otp' = authOnly ? 'phone-choice' : 'location';
	let selected = initialLocation;
	let purpose: 'signup' | 'login' = 'signup';
	let phone = '';
	let code = '';
	let challengeId = '';
	let busy = false;
	let message = '';
	$: phoneValid = /^\+[1-9][0-9]{9,14}$/.test(phone.trim());

	function chooseLocation() { step = 'phone-choice'; message = ''; }
	function finish(phoneUid?: string) { dispatch('complete', { location: selected, phoneUid }); }

	function useMyLocation() {
		message = '';
		if (!navigator.geolocation) { message = 'Location access is not available in this browser. Pick a covered city instead.'; return; }
		busy = true;
		navigator.geolocation.getCurrentPosition(({ coords }) => {
			busy = false;
			const { latitude: lat, longitude: lon } = coords;
			if (lat < SAHEL_BOUNDS.latMin || lat > SAHEL_BOUNDS.latMax || lon < SAHEL_BOUNDS.lonMin || lon > SAHEL_BOUNDS.lonMax) {
				message = 'Your current position is outside the validated forecast region. Please pick a covered city.'; return;
			}
			selected = locations.reduce((best, item) => Math.hypot(item.lat-lat,item.lon-lon) < Math.hypot(best.lat-lat,best.lon-lon) ? item : best);
			message = `${selected.name} is the nearest covered location.`;
		}, () => { busy = false; message = 'Location permission was not granted. Pick a covered city instead.'; }, { enableHighAccuracy: false, timeout: 10000 });
	}

	async function sendCode() {
		if (!phoneValid) { message = 'Use international format starting with +, for example +2348012345678.'; return; }
		busy = true; message = '';
		try {
			const result = await requestOtp(phone, purpose, deviceId);
			challengeId = result.challenge_id; step = 'otp';
		} catch (error) { message = error instanceof Error ? error.message : 'Could not send the verification code.'; }
		finally { busy = false; }
	}

	async function confirmCode() {
		busy = true; message = '';
		try {
			const result = await verifyOtp(challengeId, code, purpose === 'signup' ? selected : undefined);
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
			<p class="intro">Predictions are available only for validated locations across the Sahel. You can change this later.</p>
			<button class="locate" disabled={busy} on:click={useMyLocation}><LocateFixed size={19}/>{busy ? 'Checking location…' : 'Use my current location'}</button>
			<label for="covered-location">Covered locations</label>
			<select id="covered-location" bind:value={selected}>{#each locations as location}<option value={location}>{location.name}, {location.country}</option>{/each}</select>
			{#if message}<p class="message" role="status">{message}</p>{/if}
			<button class="primary" on:click={chooseLocation}>Continue with {selected.name}<ArrowRight size={18}/></button>
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
			<p class="intro">Use international E.164 format beginning with +. Your verified number becomes your unique SahelWatch account ID.</p>
			<label for="phone">International phone number</label><input id="phone" type="tel" autocomplete="tel" bind:value={phone} placeholder="+2348012345678" aria-describedby="phone-help" on:blur={() => { if (phone && !phoneValid) message='Use international format starting with +, for example +2348012345678.'; }} /><small id="phone-help" class="helper">Include +, country code and subscriber number. Do not start with a local 0.</small>
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
	label{display:block;margin:20px 0 8px;font-size:.78rem;font-weight:700}select,input{width:100%;min-height:52px;padding:0 15px;border:1px solid var(--border);border-radius:16px;color:var(--text);background:var(--surface-solid);font-size:1rem}.otp{font-size:1.5rem;letter-spacing:.3em;text-align:center;font-variant-numeric:tabular-nums}
	.helper{display:block;margin:7px 3px 0;color:var(--text-tertiary);font-size:.72rem;line-height:1.45}
	button{min-height:48px;border:0;border-radius:16px;font:inherit;font-weight:700;cursor:pointer}button:disabled{opacity:.45;cursor:not-allowed}.primary,.secondary,.locate,.text{width:100%;margin-top:12px}.primary{display:flex;align-items:center;justify-content:center;gap:8px;color:white;background:var(--blue)}.secondary,.locate{display:flex;align-items:center;justify-content:center;gap:8px;color:var(--text);background:var(--surface-muted)}.locate{margin-bottom:18px}.text{color:var(--text-secondary);background:transparent}.back,.close{position:absolute;top:24px;width:44px;background:var(--surface-muted)}.back{right:24px}.close{right:24px}.benefit{padding:16px;display:flex;gap:12px;border-radius:18px;background:var(--surface-muted)}.benefit p{margin:5px 0 0;color:var(--text-secondary);font-size:.8rem;line-height:1.45}.message{margin:12px 0 0;color:var(--text-secondary);font-size:.82rem}.error{color:var(--red)}.privacy{margin:24px 0 0;color:var(--text-tertiary);font-size:.72rem;line-height:1.5}.privacy a{color:var(--blue)}
	@media(prefers-reduced-motion:no-preference){.sheet{animation:enter .25s ease-out}@keyframes enter{from{opacity:0;transform:translateY(14px) scale(.98)}}}
</style>
