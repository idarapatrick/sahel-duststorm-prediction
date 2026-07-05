"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RiskIndicator } from "@/components/forecast/RiskIndicator";
import { ForecastCard } from "@/components/forecast/ForecastCard";
import { LocationSearch } from "@/components/forecast/LocationSearch";
import { RECOMMENDATIONS } from "@/lib/riskStyles";
import { getLocationPrediction, getMultiDayForecast } from "@/lib/api";
import { KNOWN_LOCATIONS, type KnownLocation } from "@/lib/locations";
import type { LocationPrediction, MultiDayForecast } from "@/lib/types";
import { Loader2, Share2 } from "lucide-react";

type Status = "loading" | "ready" | "error";

export default function LocationPage() {
  const [selected, setSelected] = useState<KnownLocation>(KNOWN_LOCATIONS[0]);
  const [prediction, setPrediction] = useState<LocationPrediction | null>(null);
  const [predictionStatus, setPredictionStatus] = useState<Status>("loading");
  const [forecast, setForecast] = useState<MultiDayForecast | null>(null);
  const [forecastStatus, setForecastStatus] = useState<Status>("loading");

  // The 3-day forecast does 3x the work of a single prediction (~15-20s
  // each), so it's fetched independently -- the risk indicator shouldn't
  // wait on it.
  useEffect(() => {
    let cancelled = false;
    setPredictionStatus("loading");
    setPrediction(null);

    getLocationPrediction(selected.lat, selected.lon).then((pred) => {
      if (cancelled) return;
      setPrediction(pred);
      setPredictionStatus(pred ? "ready" : "error");
    });

    return () => {
      cancelled = true;
    };
  }, [selected]);

  useEffect(() => {
    let cancelled = false;
    setForecastStatus("loading");
    setForecast(null);

    getMultiDayForecast(selected.lat, selected.lon, 3).then((days) => {
      if (cancelled) return;
      setForecast(days);
      setForecastStatus(days ? "ready" : "error");
    });

    return () => {
      cancelled = true;
    };
  }, [selected]);

  const shareText = prediction
    ? `SahelDust: ${prediction.risk} dust risk forecast in ${prediction.locationName} (${(prediction.probability * 100).toFixed(0)}% probability, as of ${prediction.predictionDate}).`
    : "";

  function handleShare() {
    if (navigator.share) {
      navigator.share({ text: shareText }).catch(() => {});
    } else {
      window.open(`https://wa.me/?text=${encodeURIComponent(shareText)}`, "_blank");
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-6 px-5 pt-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">My Location</h1>
        <p className="text-sm text-muted-foreground">Search a town or use your current area</p>
      </div>

      <LocationSearch onSelect={setSelected} />

      <div className="flex flex-col items-center gap-3">
        <p className="text-sm text-muted-foreground">
          {prediction?.locationName ?? `${selected.name}, ${selected.country}`}
        </p>

        {predictionStatus === "loading" && (
          <div className="flex flex-col items-center gap-2 py-6 text-muted-foreground">
            <Loader2 className="size-6 animate-spin" />
            <p className="text-xs">
              Fetching live prediction — first call for a new location can take up to 30s
            </p>
          </div>
        )}

        {predictionStatus === "error" && (
          <div className="flex flex-col items-center gap-1 rounded-2xl border border-border/60 px-6 py-5 text-center">
            <p className="text-sm font-medium">Couldn&apos;t reach the live forecast service</p>
            <p className="text-xs text-muted-foreground">
              Make sure the backend is running, or try again shortly.
            </p>
          </div>
        )}

        {predictionStatus === "ready" && prediction && (
          <>
            <RiskIndicator risk={prediction.risk} probability={prediction.probability} />
            <p className="text-xs text-muted-foreground">
              As of {prediction.predictionDate} &middot; {prediction.dataSource}
            </p>
            {prediction.dustEvent && (
              <p className="text-xs font-medium text-risk-severe">Dust event detected</p>
            )}
          </>
        )}
      </div>

      {forecastStatus === "loading" && (
        <div className="flex items-center justify-center gap-2 py-2 text-xs text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Fetching 3-day forecast (this one takes a bit longer)...
        </div>
      )}

      {forecastStatus === "ready" && forecast && (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {forecast.days.map((day, i) => (
            <ForecastCard
              key={day.date}
              forecast={day}
              label={i === 0 ? "Tomorrow" : `Day ${i + 1}`}
            />
          ))}
        </div>
      )}

      {predictionStatus === "ready" && prediction && (
        <Card className="border-border/60 bg-white/80 p-4">
          <p className="text-sm font-medium">Recommended action</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {RECOMMENDATIONS[prediction.risk]}
          </p>
        </Card>
      )}

      <Button
        variant="outline"
        className="gap-2"
        onClick={handleShare}
        disabled={predictionStatus !== "ready"}
      >
        <Share2 className="size-4" />
        Share forecast
      </Button>
    </div>
  );
}
