"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { useSelectedLocation } from "@/components/providers/LocationProvider";
import { getLocationPrediction, getMultiDayForecast, getProgressivePrediction } from "@/lib/api";
import type { LocationPrediction, MultiDayForecast, ProgressivePrediction } from "@/lib/types";

const POLL_MS = 90_000;
const SWITCH_EXPECTED_MS = 12_000;

interface CacheEntry {
  prediction: LocationPrediction | null;
  progressive: ProgressivePrediction | null;
  week: MultiDayForecast | null;
}

const EMPTY_ENTRY: CacheEntry = { prediction: null, progressive: null, week: null };

interface PredictionContextValue extends CacheEntry {
  /** True only while fetching a location that has never been seen this session -- everywhere else (tab switches, background refresh) reuses the cache instantly. */
  switching: boolean;
  switchProgress: number;
  /** True only when a brand-new location's first fetch fails with nothing to fall back on. */
  error: boolean;
  refresh: () => void;
}

const PredictionContext = createContext<PredictionContextValue | null>(null);

/**
 * The backend already runs predictions continuously from live data, so the
 * app should behave like it's reading a dashboard, not triggering a new
 * computation every time it's opened. This holds one cache per location,
 * shared across every page (Today, Tracking, ...): switching tabs for the
 * *same* location is instant and never shows a loading state, since both
 * pages read the same cached entry. Only a location the app has genuinely
 * never fetched shows the in-progress indicator.
 */
export function PredictionProvider({ children }: { children: React.ReactNode }) {
  const { location } = useSelectedLocation();
  const cache = useRef(new Map<string, CacheEntry>());
  const locKey = `${location.lat},${location.lon}`;

  const [entry, setEntry] = useState<CacheEntry>(() => cache.current.get(locKey) ?? EMPTY_ENTRY);
  const [switching, setSwitching] = useState(false);
  const [switchProgress, setSwitchProgress] = useState(0);
  const [error, setError] = useState(false);
  const [refreshNonce, setRefreshNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout> | null = null;
    let progressTimer: ReturnType<typeof setInterval> | null = null;

    const cached = cache.current.get(locKey);
    const isFreshLocation = !cached;

    // A location we've already fetched this session swaps in instantly, in
    // full. A genuinely new location instead leaves the previous location's
    // values on screen -- applyPartial below fills them in field by field as
    // the new location's own data arrives, rather than blanking everything
    // the moment any one of its three requests resolves.
    if (cached) setEntry(cached);
    setError(false);

    function stopProgress() {
      if (progressTimer) clearInterval(progressTimer);
      progressTimer = null;
    }

    function applyPartial(partial: Partial<CacheEntry>) {
      cache.current.set(locKey, { ...(cache.current.get(locKey) ?? EMPTY_ENTRY), ...partial });
      if (!cancelled) setEntry((prev) => ({ ...prev, ...partial }));
    }

    async function run(isFirstCall: boolean) {
      const showProgress = isFreshLocation && isFirstCall;
      if (showProgress) {
        setSwitching(true);
        setSwitchProgress(4);
        const start = Date.now();
        progressTimer = setInterval(() => {
          setSwitchProgress(Math.min(96, ((Date.now() - start) / SWITCH_EXPECTED_MS) * 100));
        }, 150);
      }

      // Sequenced, not concurrent: this backend resolves each of these on a
      // single worker, so firing them together starves the fastest one
      // (the current-conditions prediction) behind the slowest (the 7-day
      // forecast, which alone can take over a minute).
      const prediction = await getLocationPrediction(location.lat, location.lon);
      if (cancelled) return;
      applyPartial({ prediction });
      if (!prediction && showProgress) setError(true);

      // Today's hero needs `prediction`, Tracking's needs `progressive` -- the
      // progress indicator stays up until both are in, so neither page's
      // hero card is left showing a bare skeleton right after the bar
      // disappears.
      const progressive = await getProgressivePrediction(location.lat, location.lon);
      if (cancelled) return;
      applyPartial({ progressive });

      if (showProgress) {
        stopProgress();
        setSwitchProgress(100);
        setTimeout(() => {
          if (!cancelled) setSwitching(false);
        }, 350);
      }

      // The 7-day forecast is daily-granularity and expensive to recompute
      // (each day is resolved sequentially against GEE), so it's fetched
      // once per location rather than on every 90s poll.
      if (!cache.current.get(locKey)?.week) {
        const week = await getMultiDayForecast(location.lat, location.lon, 7);
        if (cancelled) return;
        applyPartial({ week });
      }

      pollTimer = setTimeout(() => run(false), POLL_MS);
    }

    run(true);

    return () => {
      cancelled = true;
      stopProgress();
      if (pollTimer) clearTimeout(pollTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locKey, refreshNonce]);

  const refresh = () => setRefreshNonce((n) => n + 1);

  return (
    <PredictionContext.Provider value={{ ...entry, switching, switchProgress, error, refresh }}>
      {children}
    </PredictionContext.Provider>
  );
}

export function usePrediction() {
  const ctx = useContext(PredictionContext);
  if (!ctx) throw new Error("usePrediction must be used within PredictionProvider");
  return ctx;
}
