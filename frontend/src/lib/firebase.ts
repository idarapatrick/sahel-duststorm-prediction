import { browser } from '$app/environment';
import { env } from '$env/dynamic/public';
import { getApp, getApps, initializeApp } from 'firebase/app';
import { RecaptchaVerifier, getAuth, signInWithPhoneNumber, signOut } from 'firebase/auth';
import type { ConfirmationResult } from 'firebase/auth';

export function firebaseAuthEnabled() {
	return (env.PUBLIC_AUTH_PROVIDER || 'firebase') === 'firebase' && Boolean(
		env.PUBLIC_FIREBASE_API_KEY && env.PUBLIC_FIREBASE_PROJECT_ID && env.PUBLIC_FIREBASE_APP_ID
	);
}

export function legacyPhoneAuthEnabled() {
	return env.PUBLIC_AUTH_PROVIDER === 'legacy_otp';
}

function auth() {
	if (!browser || !firebaseAuthEnabled()) throw new Error('Firebase phone verification is not configured.');
	const app = getApps().length ? getApp() : initializeApp({
		apiKey: env.PUBLIC_FIREBASE_API_KEY,
		authDomain: env.PUBLIC_FIREBASE_AUTH_DOMAIN,
		projectId: env.PUBLIC_FIREBASE_PROJECT_ID,
		appId: env.PUBLIC_FIREBASE_APP_ID,
		messagingSenderId: env.PUBLIC_FIREBASE_MESSAGING_SENDER_ID
	});
	return getAuth(app);
}

let verifier: RecaptchaVerifier | null = null;

/**
 * Convert Firebase phone-auth failures into guidance that is useful to
 * SahelWatch users and deployment maintainers without exposing provider detail.
 */
function phoneAuthError(error: unknown): Error {
	const code = typeof error === 'object' && error && 'code' in error
		? String((error as { code?: unknown }).code)
		: '';
	console.error('Firebase phone verification failed', error, {
		projectId: env.PUBLIC_FIREBASE_PROJECT_ID || 'not-configured',
		authDomain: env.PUBLIC_FIREBASE_AUTH_DOMAIN || 'not-configured'
	});
	const messages: Record<string, string> = {
		'auth/app-not-authorized': 'Phone verification is not authorised for this website.',
		'auth/auth-domain-config-required': 'The Firebase authentication domain is missing from this deployment.',
		'auth/billing-not-enabled': 'Real SMS verification requires Firebase billing to be enabled.',
		'auth/captcha-check-failed': 'The security check could not be completed. Refresh the page and try again.',
		'auth/internal-error': 'Firebase could not process this phone verification request. Check the browser console for the provider response.',
		'auth/invalid-api-key': 'The deployed Firebase API key is invalid or restricted from using Firebase Authentication.',
		'auth/invalid-app-credential': 'The website security check has expired. Refresh the page and try again.',
		'auth/invalid-recaptcha-action': 'Firebase rejected the website security-check action. Refresh the page and try again.',
		'auth/invalid-recaptcha-token': 'The website security check was rejected. Refresh the page and try again.',
		'auth/invalid-phone-number': 'Enter a valid international phone number beginning with + and the country code.',
		'auth/missing-app-credential': 'Firebase did not receive the required website security credential. Refresh the page and try again.',
		'auth/missing-phone-number': 'Enter the phone number that should receive the verification code.',
		'auth/missing-recaptcha-token': 'The website security check did not complete. Refresh the page and try again.',
		'auth/network-request-failed': 'The browser could not reach Firebase. Check the connection or privacy-blocking extensions and try again.',
		'auth/operation-not-allowed': 'The deployed Firebase configuration rejected phone verification. Please check that this app is connected to the project where Phone sign-in is enabled.',
		'auth/operation-not-supported-in-this-environment': 'This browser has blocked a feature required for phone verification.',
		'auth/quota-exceeded': 'The SMS verification limit has been reached. Please try again later.',
		'auth/recaptcha-not-enabled': 'Firebase phone authentication requires reCAPTCHA to be available for this web app.',
		'auth/too-many-requests': 'Too many verification attempts were made. Please wait before trying again.',
		'auth/unauthorized-domain': 'This website domain is not authorised in Firebase Authentication.',
		'auth/code-expired': 'This verification code has expired. Request a new code.',
		'auth/invalid-verification-code': 'The verification code is incorrect.'
	};
	return new Error(messages[code] || `Firebase verification failed (${code || 'unknown error'}). Check the browser console for details.`);
}

export async function startFirebasePhoneVerification(phone: string, containerId: string): Promise<ConfirmationResult> {
	verifier?.clear();
	// A visible challenge makes phone verification understandable and gives
	// privacy-focused browsers an explicit opportunity to complete reCAPTCHA.
	verifier = new RecaptchaVerifier(auth(), containerId, { size: 'normal' });
	try {
		return await signInWithPhoneNumber(auth(), phone, verifier);
	} catch (error) {
		verifier.clear(); verifier = null;
		throw phoneAuthError(error);
	}
}

export async function finishFirebasePhoneVerification(confirmation: ConfirmationResult, code: string) {
	try {
		const credential = await confirmation.confirm(code);
		return { idToken: await credential.user.getIdToken(true), phone: credential.user.phoneNumber };
	} catch (error) {
		throw phoneAuthError(error);
	}
}

export async function signOutFirebase() {
	if (firebaseAuthEnabled()) await signOut(auth());
}
