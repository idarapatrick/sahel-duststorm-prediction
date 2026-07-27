<svelte:head>
	<title>Terms of Use | SahelWatch</title>
	<meta name="description" content="Terms governing use of the SahelWatch research dust-event early-awareness service." />
</svelte:head>

<main>
	<a class="back" href="/?tab=settings">← Back to Settings</a>
	<p class="eyebrow">Legal</p>
	<h1>Terms of Use</h1>
	<p class="updated">Last updated: 27 July 2026</p>

	<p>By accessing or using SahelWatch, you agree to these terms. If you do not agree, do not use the service.</p>

	<h2>What SahelWatch is</h2>
	<p>SahelWatch is a research-based dust-event early-awareness platform developed as a capstone project at African Leadership University. It combines atmospheric forecasts, model analyses, satellite information and a trained machine-learning model to estimate daily dust-event probability for supported geographic forecast cells across the African Sahel.</p>

	<h2>What SahelWatch is not</h2>
	<p>SahelWatch is not a national meteorological service, government agency, emergency-management authority or certified operational warning service. It does not issue official warnings, evacuation orders, medical advice or emergency instructions. It is a supplementary research tool and not a replacement for information from national meteorological services or public-safety authorities.</p>

	<h2>Prediction limitations</h2>
	<p>Predictions are probabilistic estimates, not statements of certainty. SahelWatch can miss real events, produce false alerts, become temporarily unavailable or display a delayed central update. Users must not rely on it as their sole source of weather, health, travel, agricultural or emergency information.</p>
	<p>The current production model produces a daily binary dust-event probability. The application supports present-day and next-day central outlooks by applying that model to the relevant target-day input windows. It does not provide independently validated 12-hour, 24-hour, 36-hour and 48-hour model outputs. Any additional horizon shown as pending or unavailable is not a prediction.</p>
	<p>Aerosol optical depth measures airborne particle loading but cannot by itself distinguish mineral dust from smoke, pollution, sea salt or every other aerosol. Coastal, urban and cloudy conditions can therefore affect interpretation. SMAP and MODIS satellite products can also arrive late or contain missing and rejected pixels. SahelWatch identifies observations, delayed observations, analyses, forecasts, fallbacks and missing fields where this information is available.</p>

	<h2>Central predictions and updates</h2>
	<p>SahelWatch prepares predictions centrally for shared forecast cells. Opening the application or changing location normally retrieves the latest stored result rather than initiating a private model run. Background services may revise a result when newer evidence is available. A revision can increase or decrease estimated risk.</p>
	<p>The presence of a supported place in the coverage catalogue does not guarantee that every environmental field or prediction will be available at every time. Locations marked provisional remain subject to local performance evaluation.</p>

	<h2>Maps and tracking</h2>
	<p>Map risk areas and wind corridors are contextual visualisations. They are not verified storm boundaries, guaranteed storm paths, safe zones or evacuation routes. Do not use the map to make evacuation or route-safety decisions.</p>

	<h2>Alerts and SMS</h2>
	<p>In-app alerts are generated from configured risk thresholds and available central results. Clear conditions should not create a dust-warning alert. A linked phone account may save location and risk-threshold preferences for future SMS alerts.</p>
	<p>SMS delivery is a separately configured service and may not be active in every deployment. When enabled, delivery can be delayed, blocked or fail because of mobile-network availability, provider restrictions, destination-country rules, account configuration or circumstances outside SahelWatch’s control. Linking a number does not guarantee receipt of a message.</p>
	<p>SahelWatch does not currently claim that every alert has been reviewed by a WMO-affiliated operator. Users must consult official meteorological and emergency authorities for verified public warnings.</p>

	<h2>Phone accounts</h2>
	<p>Creating a phone account is optional. Phone ownership is verified through Firebase Authentication, and the verified number becomes the account identifier. You are responsible for maintaining control of that number and for signing out of devices you no longer use.</p>
	<p>If you lose or change your number, stop using the old identity and follow the available account-deletion or support process. SahelWatch is not responsible for messages delivered to a number that has been reassigned after you lost control of it.</p>

	<h2>Account deletion</h2>
	<p>Deletion requires recent phone verification. After confirmation, SahelWatch immediately deactivates the account, revokes its active sessions and excludes it from SMS recipients. Permanent deletion is scheduled after a seven-day grace period. Shared geographic prediction records are not personal account records and are not removed with an account.</p>

	<h2>Acceptable use</h2>
	<p>You agree not to:</p>
	<ul>
		<li>Use SahelWatch to create or distribute deliberately false emergency information.</li>
		<li>Impersonate another person or attempt to access a phone account you do not control.</li>
		<li>Interfere with the service, workers, model endpoint, database or security controls.</li>
		<li>Evade rate limits or submit automated traffic that harms service availability.</li>
		<li>Probe for credentials, private records or vulnerabilities without written authorisation.</li>
		<li>Misrepresent research predictions as official government or meteorological warnings.</li>
		<li>Use the service in violation of applicable law or a provider’s terms.</li>
	</ul>

	<h2>Availability and changes</h2>
	<p>SahelWatch may change, suspend or remove features as the research, model, providers and hosting architecture evolve. The service may be interrupted by maintenance, upstream-data delays, hosting cold starts, provider outages, network failures or security controls. Continuous or error-free availability is not guaranteed.</p>

	<h2>Third-party services and data</h2>
	<p>SahelWatch depends on external platforms and data providers, including Firebase, Google Earth Engine, DigitalOcean, Render, Vercel, Hugging Face, Open-Meteo, CAMS, SMAP and MODIS. Their services and datasets remain governed by their respective terms, licences and availability policies. SahelWatch does not claim ownership of third-party environmental data.</p>

	<h2>Intellectual property</h2>
	<p>The SahelWatch application, project-specific source code, documentation, model artefacts, branding and interface remain subject to the ownership and licence notices published with their repositories. Third-party libraries, platforms and datasets retain their own licences and rights. Access to the public application does not transfer ownership of any underlying software, model or data.</p>

	<h2>No warranty</h2>
	<p>SahelWatch is provided “as is” and “as available,” without warranties of accuracy, availability, fitness for a particular purpose or non-infringement, to the extent permitted by law.</p>

	<h2>Limitation of liability</h2>
	<p>To the extent permitted by law, the project developer and African Leadership University are not liable for injury, loss, damage, missed events, false alerts, delayed messages, unavailable data, interrupted service or decisions made in reliance on SahelWatch. Always follow official instructions from relevant meteorological, health and emergency authorities.</p>

	<h2>Privacy</h2>
	<p>Use of personal and technical information is described in the <a href="/privacy">Privacy Policy</a>, which forms part of these terms.</p>

	<h2>Changes to these terms</h2>
	<p>SahelWatch may update these terms as the project changes. The revised version will be published in the application with a new “last updated” date. Continued use after publication means you accept the revised terms.</p>

	<h2>Governing law</h2>
	<p>To the extent applicable, these terms are governed by the laws of the Republic of Rwanda, without limiting any mandatory rights that apply under another relevant jurisdiction.</p>

	<h2>Contact</h2>
	<p>Questions about these terms may be submitted to the project maintainer through the contact channel published with the SahelWatch repository or deployment.</p>
</main>

<style>
	main{width:min(780px,calc(100% - 32px));margin:auto;padding:60px 0 90px;line-height:1.75}
	.back,a{color:var(--blue);font-weight:650}
	.eyebrow{margin:34px 0 8px;color:var(--blue);font-size:.76rem;font-weight:750;letter-spacing:.09em;text-transform:uppercase}
	h1{margin:0;font-size:clamp(2.5rem,7vw,4.5rem);letter-spacing:-.055em;line-height:1}
	.updated{margin:14px 0 34px;color:var(--text-tertiary);font-size:.82rem}
	h2{margin:38px 0 8px;font-size:1.35rem;letter-spacing:-.02em}
	p,li{color:var(--text-secondary)}
	ul{padding-left:22px}
	li+li{margin-top:7px}
</style>
