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
	console.error('Firebase phone verification failed', {
		code: code || 'unknown',
		projectId: env.PUBLIC_FIREBASE_PROJECT_ID || 'not-configured',
		authDomain: env.PUBLIC_FIREBASE_AUTH_DOMAIN || 'not-configured'
	});
	const messages: Record<string, string> = {
		'auth/app-not-authorized': 'Phone verification is not authorised for this website.',
		'auth/billing-not-enabled': 'Real SMS verification requires Firebase billing to be enabled.',
		'auth/captcha-check-failed': 'The security check could not be completed. Refresh the page and try again.',
		'auth/invalid-app-credential': 'The website security check has expired. Refresh the page and try again.',
		'auth/invalid-phone-number': 'Enter a valid international phone number beginning with + and the country code.',
		'auth/missing-phone-number': 'Enter the phone number that should receive the verification code.',
		'auth/operation-not-allowed': 'The deployed Firebase configuration rejected phone verification. Please check that this app is connected to the project where Phone sign-in is enabled.',
		'auth/quota-exceeded': 'The SMS verification limit has been reached. Please try again later.',
		'auth/too-many-requests': 'Too many verification attempts were made. Please wait before trying again.',
		'auth/code-expired': 'This verification code has expired. Request a new code.',
		'auth/invalid-verification-code': 'The verification code is incorrect.'
	};
	return new Error(messages[code] || 'The verification message could not be sent. Please try again.');
}

export async function startFirebasePhoneVerification(phone: string, containerId: string): Promise<ConfirmationResult> {
	verifier?.clear();
	verifier = new RecaptchaVerifier(auth(), containerId, { size: 'invisible' });
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
