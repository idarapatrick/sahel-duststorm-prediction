/**
 * Optional, local-only phone verification for alerts. There's no account
 * system -- the app is open by default. Linking a phone is just: enter a
 * number, "verify" a 6-digit code (any 6 digits work, no backend OTP yet),
 * and remember it on this device.
 */

const LINKED_PHONE_KEY = "saheldust:linked-phone";

export function getLinkedPhone(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(LINKED_PHONE_KEY);
}

export function linkPhone(phone: string) {
  window.localStorage.setItem(LINKED_PHONE_KEY, phone);
}

export function unlinkPhone() {
  window.localStorage.removeItem(LINKED_PHONE_KEY);
}

export function isValidCode(code: string): boolean {
  return /^\d{6}$/.test(code);
}
