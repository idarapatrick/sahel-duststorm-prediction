"use client";

import { useEffect, useState } from "react";
import { Navigation as Crosshair, MapPin, Sun, Cloud, Wind, Tornado } from "lucide-react";
import { Card } from "@/components/ui/card";
import { DustySky } from "@/components/layout/DustySky";
import { LocationSearch } from "@/components/forecast/LocationSearch";
import { StormSpreadMap } from "@/components/forecast/StormSpreadMap";
import { useSelectedLocation } from "@/components/providers/LocationProvider";
import { getMultiDayForecast } from "@/lib/api";
import type { MultiDayForecast, RiskLevel } from "@/lib/types";
import { RISK_LABEL } from "@/lib/riskStyles";

const RISK_HEX: Record<RiskLevel, string> = {
  low: "#6FCF97",
  moderate: "#F2C14E",
  high: "#F0883E",
  severe: "#E5533B",
};

const DAY_ICON: Record<RiskLevel, typeof Sun> = {
  low: Sun,
  moderate: Cloud,
  high: Wind,
  severe: Tornado,
};

const DAY_TINT: Record<RiskLevel, string> = {
  low: "rgba(111,207,151,.16)",
  moderate: "rgba(242,193,78,.16)",
  high: "rgba(240,136,62,.16)",
  severe: "rgba(229,83,59,.16)",
};

export default function MyAreaPage() {
  const { location, setLocation } = useSelectedLocation();
  const [forecast, setForecast] = useState<MultiDayForecast | null>(null);

  useEffect(() => {
    let cancelled = false;
    setForecast(null);
    getMultiDayForecast(location.lat, location.lon, 3).then((data) => {
      if (!cancelled) setForecast(data);
    });
    return () => {
      cancelled = true;
    };
  }, [location]);

  function useMyLocation() {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition((pos) => {
      setLocation({
        name: "My location",
        country: "",
        lat: pos.coords.latitude,
        lon: pos.coords.longitude,
      });
    });
  }

  return (
    <DustySky glow="left">
      <div className="flex flex-1 flex-col gap-4 px-[18px] pt-2">
        <p className="sky-text text-2xl font-extrabold text-sd-strong">My area</p>

        <LocationSearch onSelect={setLocation} />

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-[7px]">
            <MapPin className="sky-icon size-4 text-[#F2C14E]" />
            <span className="sky-text text-[15px] font-bold text-sd-strong">
              {location.name}
              {location.country ? `, ${location.country}` : ""}
            </span>
          </div>
          <button
            onClick={useMyLocation}
            className="flex items-center gap-[6px] rounded-[14px] border px-[11px] py-[7px]"
            style={{ background: "rgba(20,26,32,.58)", borderColor: "rgba(255,255,255,.13)" }}
          >
            <Crosshair className="size-[14px] text-sd-primary" />
            <span className="text-[11px] font-bold text-sd-primary">Use my location</span>
          </button>
        </div>

        <Card className="rounded-[24px] border-[rgba(255,255,255,.2)] p-5 shadow-[0_14px_34px_rgba(0,0,0,0.26)]">
          <StormSpreadMap />
        </Card>

        <p className="sky-text mt-0.5 text-[13px] font-bold text-sd-primary">Next 3 days</p>
        <div className="flex gap-2.5">
          {forecast ? (
            forecast.days.map((day, i) => {
              const Icon = DAY_ICON[day.risk];
              const labels = ["Sat", "Sun", "Mon"];
              return (
                <Card key={day.date} className="flex-1 items-center gap-[7px] p-[14px_8px]">
                  <span className="text-xs font-semibold text-sd-muted">{labels[i] ?? day.date}</span>
                  <span
                    className="flex size-[34px] items-center justify-center rounded-full"
                    style={{ background: DAY_TINT[day.risk] }}
                  >
                    <Icon className="size-[17px]" style={{ color: RISK_HEX[day.risk] }} />
                  </span>
                  <span className="text-xs font-extrabold" style={{ color: RISK_HEX[day.risk] }}>
                    {RISK_LABEL[day.risk]}
                  </span>
                  <span className="text-[15px] font-extrabold text-sd-strong">
                    {(day.probability * 100).toFixed(0)}%
                  </span>
                </Card>
              );
            })
          ) : (
            <p className="text-xs text-sd-muted">Loading forecast...</p>
          )}
        </div>
      </div>
    </DustySky>
  );
}
