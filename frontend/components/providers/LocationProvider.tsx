"use client";

import { createContext, useContext, useLayoutEffect, useState } from "react";
import { KNOWN_LOCATIONS, type KnownLocation } from "@/lib/locations";
import { getSavedLocation, saveLocation } from "@/lib/onboarding";

const LocationContext = createContext<{
  location: KnownLocation;
  setLocation: (location: KnownLocation) => void;
} | null>(null);

const DEFAULT_LOCATION =
  KNOWN_LOCATIONS.find((loc) => loc.name === "Niamey") ?? KNOWN_LOCATIONS[0];

export function LocationProvider({ children }: { children: React.ReactNode }) {
  // Starts at DEFAULT_LOCATION on every render (server and client alike) so
  // the first paint always matches -- localStorage isn't available during
  // SSR, so reading it in the initializer would make the client's first
  // render disagree with the server's and trigger a hydration mismatch. The
  // saved location (if any) is applied right after mount instead.
  const [location, setLocationState] = useState<KnownLocation>(DEFAULT_LOCATION);

  // useLayoutEffect (not useEffect) so a returning user's saved location
  // swaps in before the browser paints -- no visible flash of the default.
  useLayoutEffect(() => {
    const saved = getSavedLocation();
    if (saved) setLocationState(saved);
  }, []);

  function setLocation(next: KnownLocation) {
    setLocationState(next);
    saveLocation(next);
  }

  return (
    <LocationContext.Provider value={{ location, setLocation }}>
      {children}
    </LocationContext.Provider>
  );
}

export function useSelectedLocation() {
  const ctx = useContext(LocationContext);
  if (!ctx) throw new Error("useSelectedLocation must be used within LocationProvider");
  return ctx;
}
