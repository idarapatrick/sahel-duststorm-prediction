import type { KnownLocation } from "@/lib/locations";

const ONBOARDED_KEY = "saheldust:onboarded";
const LOCATION_KEY = "saheldust:location";

export function hasOnboarded(): boolean {
  if (typeof window === "undefined") return true;
  return window.localStorage.getItem(ONBOARDED_KEY) === "1";
}

export function completeOnboarding(location: KnownLocation) {
  window.localStorage.setItem(ONBOARDED_KEY, "1");
  saveLocation(location);
}

export function saveLocation(location: KnownLocation) {
  window.localStorage.setItem(LOCATION_KEY, JSON.stringify(location));
}

export function getSavedLocation(): KnownLocation | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(LOCATION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (typeof parsed?.lat === "number" && typeof parsed?.lon === "number" && typeof parsed?.name === "string") {
      return parsed as KnownLocation;
    }
    return null;
  } catch {
    return null;
  }
}
