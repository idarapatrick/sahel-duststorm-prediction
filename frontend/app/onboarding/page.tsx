"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Navigation as Crosshair, Wind, MapPin, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { DustySky } from "@/components/layout/DustySky";
import { LocationSearch } from "@/components/forecast/LocationSearch";
import { KNOWN_LOCATIONS, type KnownLocation } from "@/lib/locations";
import { isWithinSahelBounds } from "@/lib/api";
import { completeOnboarding } from "@/lib/onboarding";

export default function OnboardingPage() {
  const router = useRouter();
  const [locating, setLocating] = useState(false);
  const [outOfCoverage, setOutOfCoverage] = useState(false);

  function choose(location: KnownLocation) {
    completeOnboarding(location);
    router.replace("/");
  }

  function useMyLocation() {
    if (!navigator.geolocation) return;
    setOutOfCoverage(false);
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude: lat, longitude: lon } = pos.coords;
        setLocating(false);
        if (!isWithinSahelBounds(lat, lon)) {
          setOutOfCoverage(true);
          return;
        }
        choose({ name: "My location", country: "", lat, lon });
      },
      () => setLocating(false)
    );
  }

  return (
    <DustySky glow="right">
      <div className="flex flex-1 flex-col gap-6 px-6 pb-8 pt-14">
        <div className="flex flex-col items-center gap-4 text-center">
          <div
            className="flex size-16 items-center justify-center rounded-[20px] shadow-[0_10px_26px_rgba(229,83,59,0.34)]"
            style={{ background: "linear-gradient(150deg,#F2C14E,#E5533B)" }}
          >
            <Wind className="size-8 text-[#20272e]" />
          </div>
          <div>
            <p className="text-2xl font-extrabold text-sd-strong">Welcome to SahelDust</p>
            <p className="mt-2 text-sm font-medium leading-[1.5] text-sd-primary">
              Simple dust-storm warnings for the Sahel. Pick your town to see today&apos;s forecast.
            </p>
          </div>
        </div>

        <Card className="gap-3 p-5">
          <button
            onClick={useMyLocation}
            disabled={locating}
            className="flex items-center justify-center gap-2 rounded-[14px] py-[13px] text-sm font-extrabold text-[#20272e] shadow-[0_8px_20px_rgba(240,136,62,0.3)] disabled:opacity-60"
            style={{ background: "linear-gradient(90deg,#F2C14E,#F0883E)" }}
          >
            {locating ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Crosshair className="size-4" />
            )}
            {locating ? "Finding you..." : "Use my location"}
          </button>
          {outOfCoverage && (
            <p className="text-center text-xs font-medium leading-[1.5] text-sd-secondary">
              Your location is outside our coverage of the African Sahel region. Pick a town below instead.
            </p>
          )}
        </Card>

        <div className="flex flex-col gap-3">
          <p className="text-xs font-bold uppercase tracking-[0.02em] text-sd-label">Search a town</p>
          <LocationSearch onSelect={choose} />
        </div>

        <div className="flex flex-col gap-3">
          <p className="text-xs font-bold uppercase tracking-[0.02em] text-sd-label">Or pick from the list</p>
          <div className="flex flex-col gap-2">
            {KNOWN_LOCATIONS.map((loc) => (
              <button key={loc.name} onClick={() => choose(loc)}>
                <Card className="flex-row items-center gap-3 rounded-[16px] p-3.5">
                  <span
                    className="flex size-9 shrink-0 items-center justify-center rounded-full"
                    style={{ background: "rgba(242,193,78,.18)" }}
                  >
                    <MapPin className="size-4" style={{ color: "#F2C14E" }} />
                  </span>
                  <span className="text-sm font-semibold text-sd-strong">
                    {loc.name}
                    {loc.country ? `, ${loc.country}` : ""}
                  </span>
                </Card>
              </button>
            ))}
          </div>
        </div>
      </div>
    </DustySky>
  );
}
