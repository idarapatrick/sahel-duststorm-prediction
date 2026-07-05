"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { LocationSearch } from "@/components/forecast/LocationSearch";
import { TrendIndicator } from "@/components/forecast/TrendIndicator";
import { ALERT_BADGE_CLASS } from "@/lib/riskStyles";
import { getProgressivePrediction } from "@/lib/api";
import { KNOWN_LOCATIONS, type KnownLocation } from "@/lib/locations";
import type { ProgressivePrediction } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Loader2, RefreshCw } from "lucide-react";

type Status = "loading" | "ready" | "error";

export default function ProgressiveTrackingPage() {
  const [selected, setSelected] = useState<KnownLocation>(KNOWN_LOCATIONS[0]);
  const [data, setData] = useState<ProgressivePrediction | null>(null);
  const [status, setStatus] = useState<Status>("loading");

  function load() {
    setStatus("loading");
    getProgressivePrediction(selected.lat, selected.lon).then((result) => {
      setData(result);
      setStatus(result ? "ready" : "error");
    });
  }

  useEffect(load, [selected]);

  return (
    <div className="flex flex-1 flex-col gap-6 px-5 pt-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Progressive Tracking</h1>
        <p className="text-sm text-muted-foreground">
          Predictions get more confident as real observations replace forecast data
        </p>
      </div>

      <LocationSearch onSelect={setSelected} />

      {status === "loading" && (
        <div className="flex flex-col items-center gap-2 py-10 text-muted-foreground">
          <Loader2 className="size-6 animate-spin" />
          <p className="text-xs">Fetching progressive prediction — this can take up to 30s</p>
        </div>
      )}

      {status === "error" && (
        <Card className="border-border/60 p-5 text-center">
          <p className="text-sm font-medium">Couldn&apos;t reach the tracking service</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Make sure the backend is running, or try again shortly.
          </p>
        </Card>
      )}

      {status === "ready" && data && (
        <>
          <div className="flex flex-col items-center gap-3">
            <p className="text-sm text-muted-foreground">
              {data.locationName} &middot; target {data.targetDate}
            </p>
            <div
              className={cn(
                "flex flex-col items-center gap-1 rounded-3xl border px-8 py-6 text-center",
                ALERT_BADGE_CLASS[data.alertLevel]
              )}
            >
              <span className="text-2xl font-semibold">{data.alertLabel}</span>
              <span className="font-mono text-sm text-muted-foreground">
                {(data.probability * 100).toFixed(0)}% probability
              </span>
            </div>
            <div className="flex items-center gap-3">
              <TrendIndicator trend={data.trend} />
              <span className="text-xs text-muted-foreground">
                {data.hoursUntilEvent.toFixed(0)}h until target date
              </span>
            </div>
          </div>

          <Card className="border-border/60 bg-white/80 p-4">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">Confidence</span>
              <span className="font-mono">{data.dataComposition.confidencePct}%</span>
            </div>
            <Progress value={data.dataComposition.confidencePct} className="mt-2" />
            <p className="mt-2 text-xs text-muted-foreground">
              {data.dataComposition.description}
            </p>
          </Card>

          <Card className="border-border/60 bg-white/80 p-4">
            <p className="text-sm font-medium">Alert message</p>
            <p className="mt-1 text-sm text-muted-foreground">{data.alertMessage}</p>
          </Card>

          {data.history.length > 1 && (
            <Card className="border-border/60 bg-white/80 p-4">
              <p className="mb-3 text-sm font-medium">History ({data.history.length} updates)</p>
              <div className="flex flex-col gap-2">
                {[...data.history].reverse().map((update) => (
                  <div
                    key={update.timestamp}
                    className="flex items-center justify-between border-b border-border/40 pb-2 text-xs last:border-0 last:pb-0"
                  >
                    <span className="text-muted-foreground">
                      {new Date(update.timestamp).toLocaleString()}
                    </span>
                    <Badge
                      variant="outline"
                      className={cn("capitalize", ALERT_BADGE_CLASS[update.alertLevel])}
                    >
                      {update.alertLevel}
                    </Badge>
                    <span className="font-mono">{(update.probability * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <Button variant="outline" className="gap-2" onClick={load}>
            <RefreshCw className="size-4" />
            Refresh prediction
          </Button>
        </>
      )}
    </div>
  );
}
