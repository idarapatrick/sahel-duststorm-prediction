"use client";

import { Area, ComposedChart, Line, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { DustySky } from "@/components/layout/DustySky";
import { LocationPill } from "@/components/forecast/LocationPill";
import { usePrediction } from "@/components/providers/PredictionProvider";
import { ALERT_STATUS_LABEL } from "@/lib/riskStyles";
import type { AlertLevel } from "@/lib/types";
import { RefreshCw, TrendingDown, TrendingUp } from "lucide-react";

const ALERT_HEX: Record<AlertLevel, string> = {
  clear: "#6FCF97",
  watch: "#F2C14E",
  warning: "#F0883E",
  alert: "#E5533B",
};

function relativeDay(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffDays = Math.floor((now.setHours(0, 0, 0, 0) - date.setHours(0, 0, 0, 0)) / 86400000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays > 1) return `${diffDays} days ago`;
  return new Date(timestamp).toLocaleDateString(undefined, { weekday: "short" });
}

export default function TrackingPage() {
  const { progressive: data, switchProgress, error, refresh } = usePrediction();

  const targetWeekday = data
    ? new Date(data.targetDate).toLocaleDateString(undefined, { weekday: "long" })
    : "";
  const targetShort = data
    ? new Date(data.targetDate).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })
    : "";

  const chartData = data?.history.map((u) => ({
    label: relativeDay(u.timestamp),
    chance: Math.round(u.probability * 100),
  }));

  return (
    <DustySky glow="right">
      <div className="flex flex-1 flex-col gap-4 px-[18px] pt-2">
        <div className="sky-text">
          <p className="text-2xl font-extrabold text-sd-strong">Tracking</p>
          <p className="mt-[3px] text-[13px] font-medium text-sd-primary">
            We keep checking. The closer the day, the surer we get.
          </p>
        </div>

        <div className="sky-text flex items-center gap-2 text-[13px] font-semibold text-sd-secondary">
          <LocationPill />
          {data && (
            <span>
              watching for <span className="font-extrabold text-sd-strong">{targetShort}</span>
            </span>
          )}
        </div>

        {error && !data && (
          <Card className="items-center gap-1 p-5 text-center">
            <p className="text-sm font-medium text-sd-strong">Forecasting services are currently down</p>
            <p className="text-xs text-sd-muted">Kindly check back in some minutes.</p>
          </Card>
        )}

        {!error && (
          <Card className="items-center gap-0 rounded-[26px] border-[rgba(255,255,255,.16)] p-[18px] text-center">
            <p className="text-xs font-bold uppercase tracking-[0.02em] text-sd-label">Heads up</p>
            {data ? (
              <>
                <p
                  className="mt-1.5 mb-0.5 text-[34px] font-extrabold leading-none"
                  style={{ color: ALERT_HEX[data.alertLevel] }}
                >
                  {ALERT_STATUS_LABEL[data.alertLevel]}
                </p>
                <p className="text-sm font-semibold text-sd-primary">
                  {(data.probability * 100).toFixed(0)}% chance on {targetWeekday}
                </p>
              </>
            ) : (
              <div className="mt-2 flex w-full flex-col items-center gap-2 py-2">
                <p className="text-[34px] font-extrabold leading-none text-sd-faint">—</p>
                <Progress value={switchProgress} />
                <p className="text-xs font-semibold text-sd-muted">
                  Checking conditions for this location... {Math.round(switchProgress)}%
                </p>
              </div>
            )}
            {data && (data.trend === "increasing" || data.trend === "decreasing") && (
                <span
                  className="mt-3 inline-flex items-center gap-[6px] rounded-[14px] px-3 py-1.5"
                  style={{
                    background:
                      data.trend === "increasing" ? "rgba(229,83,59,.16)" : "rgba(111,207,151,.16)",
                  }}
                >
                  {data.trend === "increasing" ? (
                    <TrendingUp className="size-[15px]" style={{ color: "#E5533B" }} />
                  ) : (
                    <TrendingDown className="size-[15px]" style={{ color: "#6FCF97" }} />
                  )}
                  <span
                    className="text-xs font-bold"
                    style={{ color: data.trend === "increasing" ? "#F0A090" : "#9FE0BC" }}
                  >
                    {data.trend === "increasing" ? "Rising since yesterday" : "Falling since yesterday"}
                  </span>
                </span>
              )}
          </Card>
        )}

        {data && (
          <>
            <Card className="gap-3.5 p-5">
              <div className="flex items-center justify-between text-[13px]">
                <span className="font-bold text-sd-primary">How sure we are</span>
                <span className="text-[15px] font-extrabold" style={{ color: "#F2C14E" }}>
                  {data.dataComposition.confidencePct}%
                </span>
              </div>
              <Progress value={data.dataComposition.confidencePct} />
              <p className="text-xs font-medium leading-[1.5] text-sd-secondary">
                Confidence climbs as fresh readings replace early estimates. We&apos;ll keep updating
                until {targetWeekday}.
              </p>
            </Card>

            {chartData && chartData.length > 1 && (
              <Card className="gap-3.5 p-5">
                <p className="text-[13px] font-bold text-sd-primary">How the forecast changed</p>
                <div className="h-[78px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
                      <defs>
                        <linearGradient id="trackingArea" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0" stopColor="#F0883E" stopOpacity={0.42} />
                          <stop offset="1" stopColor="#F0883E" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <YAxis hide domain={[0, 100]} />
                      <Area
                        type="monotone"
                        dataKey="chance"
                        stroke="none"
                        fill="url(#trackingArea)"
                        isAnimationActive={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="chance"
                        stroke="#F0883E"
                        strokeWidth={2.5}
                        dot={false}
                        isAnimationActive={false}
                      />
                      <XAxis dataKey="label" hide />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex justify-between">
                  {chartData.map((d, i) => (
                    <span
                      key={i}
                      className="text-[10px] font-semibold"
                      style={{ color: i === chartData.length - 1 ? "#F0C48A" : "#B9C4CE" }}
                    >
                      {d.label}
                    </span>
                  ))}
                </div>
              </Card>
            )}

            <Card className="gap-3 p-5">
              <div className="flex items-center justify-between">
                <p className="text-[13px] font-bold text-sd-primary">Recent updates</p>
                <button onClick={refresh} aria-label="Refresh">
                  <RefreshCw className="size-[15px] text-sd-muted" />
                </button>
              </div>
              <div className="flex flex-col">
                {[...data.history].reverse().map((update, i, arr) => (
                  <div
                    key={update.timestamp}
                    className="flex items-center justify-between py-[9px]"
                    style={i < arr.length - 1 ? { borderBottom: "1px solid rgba(255,255,255,.08)" } : undefined}
                  >
                    <span className="text-xs font-medium text-sd-secondary">
                      {relativeDay(update.timestamp)}
                    </span>
                    <span
                      className="text-[11px] font-extrabold"
                      style={{ color: ALERT_HEX[update.alertLevel] }}
                    >
                      {ALERT_STATUS_LABEL[update.alertLevel]}
                    </span>
                    <span className="text-xs font-extrabold text-sd-strong">
                      {(update.probability * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          </>
        )}
      </div>
    </DustySky>
  );
}
