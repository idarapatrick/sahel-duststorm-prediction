<svelte:head><title>Privacy Policy | SahelWatch</title></svelte:head>

<main>
	<a href="/?tab=settings">← Back to Settings</a>
	<p class="eyebrow">Legal</p>
	<h1>Privacy Policy</h1>
	<p>SahelWatch can be used without creating a phone account. Location searches and prediction snapshots are primarily environmental records, but account and device information is processed when needed to provide personal location preferences, secure login and requested alerts.</p>
	<h2>Phone numbers and verification</h2>
	<p>A linked number is stored in normalized international format. Firebase Authentication processes the phone number and verification code and gives SahelWatch a unique identity reference after verification. SahelWatch does not store the Firebase verification code. Twilio processes phone numbers and alert messages when SMS alerts are enabled. Phone numbers are never sold.</p>
	<h2>Location and IP addresses</h2>
	<p>If you choose “Use my current location,” the browser requests location permission and SahelWatch selects the nearest monitored community. The app remains usable if permission is refused or the device is outside the configured region. Server infrastructure necessarily receives IP addresses when requests are made. SahelWatch hashes IP addresses before storing limited security and device-session metadata and may use network information to support coarse location services, abuse prevention and troubleshooting. An IP address is not used as an account ID because it may be shared or change.</p>
	<h2>Devices and sessions</h2>
	<p>A random device identifier is stored in the browser to distinguish first-device onboarding and help secure sessions. Firebase maintains the browser authentication state, while SahelWatch stores a secure, revocable application-session cookie. Logging out ends both sessions.</p>
	<h2>Optional SMS alerts</h2>
	<p>Users who do not link a phone number can still use forecasts and in-app alerts, but cannot receive SMS alerts while offline. SMS preferences can be changed by logging out, unlinking or deleting the account.</p>
	<h2>Retention and deletion</h2>
	<p>Prediction snapshots and detailed reinforcement evidence are retained for up to 90 days. Sessions and operational SMS records are retained only as needed for security, delivery reconciliation and legal obligations. Account deletion requires fresh phone verification. After confirmation, sign-ins and SMS alerts stop immediately. The phone identity, alert choices and associated account records are permanently removed after seven days. Firebase identity cleanup is retried automatically if the provider is temporarily unavailable.</p>
	<h2>Research notice</h2>
	<p>SahelWatch is a research forecasting system and is not an official emergency-warning authority.</p>
</main>

<style>main{width:min(720px,calc(100% - 32px));margin:auto;padding:60px 0;line-height:1.7}a{color:var(--blue);font-weight:650}h1{font-size:clamp(2.5rem,7vw,4.5rem);letter-spacing:-.055em}h2{margin-top:34px}p{color:var(--text-secondary)}</style>
