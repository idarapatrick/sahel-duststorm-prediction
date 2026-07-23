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

export async function startFirebasePhoneVerification(phone: string, containerId: string): Promise<ConfirmationResult> {
	verifier?.clear();
	verifier = new RecaptchaVerifier(auth(), containerId, { size: 'invisible' });
	try {
		return await signInWithPhoneNumber(auth(), phone, verifier);
	} catch (error) {
		verifier.clear(); verifier = null;
		throw error;
	}
}

export async function finishFirebasePhoneVerification(confirmation: ConfirmationResult, code: string) {
	const credential = await confirmation.confirm(code);
	return { idToken: await credential.user.getIdToken(true), phone: credential.user.phoneNumber };
}

export async function signOutFirebase() {
	if (firebaseAuthEnabled()) await signOut(auth());
}
