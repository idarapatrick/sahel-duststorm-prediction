"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { BottomSheet } from "@/components/layout/BottomSheet";
import { FORECAST_DATES, FORECAST_DATE_LABELS, getForecast } from "@/lib/api";
import type { GridPrediction } from "@/lib/types";

const ForecastMap = dynamic(
  () => import("@/components/map/ForecastMap").then((mod) => mod.ForecastMap),
  { ssr: false }
);

export default function HomePage() {
  const [dateIndex, setDateIndex] = useState(0);
  const [cells, setCells] = useState<GridPrediction[]>([]);
  const [userPosition, setUserPosition] = useState<{ lat: number; lon: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    getForecast(FORECAST_DATES[dateIndex]).then((data) => {
      if (!cancelled) setCells(data.cells);
    });
    return () => {
      cancelled = true;
    };
  }, [dateIndex]);

  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => setUserPosition({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => setUserPosition(null),
      { timeout: 5000 }
    );
  }, []);

  return (
    <div className="flex flex-1 flex-col">
      <header className="flex flex-col gap-3 px-5 pt-6 pb-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">SahelDust</h1>
            <p className="text-sm text-muted-foreground">Dust risk forecast across the Sahel</p>
          </div>
          <Badge variant="outline" className="mt-1 shrink-0 text-muted-foreground">
            Illustrative regional data
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          For a live prediction at a specific place, use My Location or Tracking below.
        </p>
        <Tabs value={String(dateIndex)} onValueChange={(v) => setDateIndex(Number(v))}>
          <TabsList className="grid w-full grid-cols-3">
            {FORECAST_DATE_LABELS.map((label, i) => (
              <TabsTrigger key={label} value={String(i)}>
                {label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </header>
      <div className="relative flex-1 overflow-hidden">
        <ForecastMap cells={cells} userPosition={userPosition} />
        {cells.length > 0 && <BottomSheet cells={cells} />}
      </div>
    </div>
  );
}
