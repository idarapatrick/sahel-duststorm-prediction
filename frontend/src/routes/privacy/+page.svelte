<svelte:head>
	<title>Privacy Policy | SahelWatch</title>
	<meta name="description" content="How SahelWatch collects, uses, protects and deletes personal information." />
</svelte:head>

<main>
	<a class="back" href="/?tab=settings">← Back to Settings</a>
	<p class="eyebrow">Legal</p>
	<h1>Privacy Policy</h1>
	<p class="updated">Last updated: 27 July 2026</p>

	<p>SahelWatch is a research dust-event early-awareness platform built for communities across the African Sahel. This policy explains what information the service processes, why it is needed, how long it is retained and what choices users have.</p>

	<h2>Information we process</h2>
	<p>SahelWatch can be used without creating a phone account. If you choose to link an account, we process your phone number in normalized international format, the identity reference issued by Firebase Authentication, your monitored locations, your selected alert thresholds and the status and time of any alert delivery attempt.</p>
	<p>The service also processes limited technical information needed to operate securely. This includes a random browser device identifier, revocable session records, request times and hashed IP-address values used for session security, rate limiting, abuse prevention and troubleshooting. Server and hosting providers may temporarily process network addresses in their infrastructure logs.</p>
	<p>SahelWatch does not request your name, email address, physical address, age, gender or demographic profile.</p>

	<h2>Location information</h2>
	<p>You may manually choose any covered community. If you select “Use my current location,” your browser asks for permission and sends coordinates so SahelWatch can identify the nearest monitored community. This feature is optional. The application remains usable if permission is refused or your position is outside the supported forecast region.</p>
	<p>The service stores the forecast location you choose, but it does not continuously track your movement or use your position to create individual dust predictions. Predictions are generated for geographic forecast cells and shared by all users requesting the same area.</p>

	<h2>Phone verification and sessions</h2>
	<p>Firebase Authentication processes the phone number, security checks and verification code. After successful verification, Firebase gives SahelWatch a signed identity token and a unique Firebase identity reference. SahelWatch verifies that token and creates a separate revocable application session in PostgreSQL. SahelWatch does not store the Firebase verification code.</p>
	<p>A random device identifier is stored in the browser to support onboarding and session security. Logging out ends the SahelWatch application session and signs the browser out of Firebase.</p>

	<h2>Why we use this information</h2>
	<ul>
		<li>To verify ownership of a linked phone number.</li>
		<li>To create and secure an optional SahelWatch account.</li>
		<li>To save monitored locations and alert thresholds.</li>
		<li>To provide in-app notifications and, when enabled, requested SMS alerts.</li>
		<li>To prevent abuse, enforce request limits and investigate service failures.</li>
		<li>To process account deletion and remove associated records.</li>
	</ul>
	<p>Phone numbers are not used for advertising, sold to data brokers or used to create personal advertising profiles.</p>

	<h2>Environmental and prediction records</h2>
	<p>SahelWatch stores environmental evidence, centrally generated prediction snapshots, revisions, provider information and delayed outcome labels. These records concern geographic grid cells rather than individual users. Phone numbers, Firebase identities, session records and IP information are not used as machine-learning training features.</p>

	<h2>Service providers</h2>
	<p>SahelWatch relies on specialist providers to operate the service. Depending on the feature used, information may be processed by Firebase and Google for authentication and satellite access, DigitalOcean for managed PostgreSQL, Render for backend services and workers, Vercel for the web application, Hugging Face for model serving, and environmental-data providers such as Open-Meteo and CAMS.</p>
	<p>Twilio may receive a destination phone number and alert-message details when production SMS alerts are enabled. SMS delivery is currently a separately configured feature and is not guaranteed merely because a phone account is linked. Providers process information under their own privacy and security terms.</p>

	<h2>How information is protected</h2>
	<p>Communication between the browser, backend and supported providers uses HTTPS or TLS. DigitalOcean Managed PostgreSQL provides encryption at rest, access controls and encrypted database connections. SahelWatch stores application IP values as one-way hashes, stores session tokens as hashes and keeps deployment credentials outside the source repository in protected environment variables.</p>
	<p>No internet-connected service can guarantee absolute security. SahelWatch limits the personal information it requests and separates identity records from environmental prediction data to reduce exposure.</p>

	<h2>Retention</h2>
	<ul>
		<li>Active phone-account and subscription records are retained while the account remains active.</li>
		<li>Prediction snapshots and detailed environmental evidence are retained for up to 90 days in the operational application database.</li>
		<li>Delivered alert and processed outbox records are removed after the configured 90-day operational period.</li>
		<li>Expired OTP challenges and sessions are removed by scheduled retention processing.</li>
		<li>Security and provider logs may follow the shorter or longer retention periods established by the relevant infrastructure provider or applicable law.</li>
	</ul>

	<h2>Your choices and rights</h2>
	<p>You may use SahelWatch without linking a phone number. If you create an account, you may change or remove alert subscriptions, log out, sign in with another verified number or request account deletion from Settings.</p>
	<p>Account deletion requires recent phone verification. Once confirmed, the account is marked for deletion, active sessions are revoked and the account is immediately excluded from SMS alert recipients. The Firebase identity, phone account and associated application records are permanently removed after a seven-day grace period. Cleanup is retried if Firebase is temporarily unavailable.</p>
	<p>Deleting a phone account does not remove non-personal environmental predictions for shared geographic cells because those predictions do not identify the account holder.</p>

	<h2>What we do not do</h2>
	<ul>
		<li>We do not continuously track users’ physical movements.</li>
		<li>We do not sell or rent phone numbers.</li>
		<li>We do not use personal account data to train the dust prediction model.</li>
		<li>We do not generate different environmental predictions based on a user’s identity.</li>
		<li>We do not use account data for targeted advertising.</li>
	</ul>

	<h2>Children</h2>
	<p>SahelWatch is not directed to children under 13 and does not knowingly collect their personal information. A parent or guardian who believes a child has linked a phone number should contact the project maintainer to request review and deletion.</p>

	<h2>Research and safety notice</h2>
	<p>SahelWatch is a research forecasting and early-awareness system. It is not a national meteorological service, emergency authority or substitute for official safety guidance.</p>

	<h2>Changes to this policy</h2>
	<p>Material changes will be published in the application with a revised “last updated” date. Where appropriate, important changes will also be communicated through the application.</p>

	<h2>Contact</h2>
	<p>Questions about this policy or an account-data request may be submitted to the project maintainer through the contact channel published with the SahelWatch repository or deployment.</p>
</main>

<style>
	main{width:min(780px,calc(100% - 32px));margin:auto;padding:60px 0 90px;line-height:1.75}
	.back{color:var(--blue);font-weight:650}
	.eyebrow{margin:34px 0 8px;color:var(--blue);font-size:.76rem;font-weight:750;letter-spacing:.09em;text-transform:uppercase}
	h1{margin:0;font-size:clamp(2.5rem,7vw,4.5rem);letter-spacing:-.055em;line-height:1}
	.updated{margin:14px 0 34px;color:var(--text-tertiary);font-size:.82rem}
	h2{margin:38px 0 8px;font-size:1.35rem;letter-spacing:-.02em}
	p,li{color:var(--text-secondary)}
	ul{padding-left:22px}
	li+li{margin-top:7px}
</style>
