"use client";

import Link from "next/link";
import {
  Bell,
  Settings,
  Eye,
  Wind,
  Sparkles,
  Droplets,
  Home,
  Droplet,
  Shield,
  Car,
  Clock,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronRight,
  Lightbulb,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { DustySky } from "@/components/layout/DustySky";
import { LocationPill } from "@/components/forecast/LocationPill";
import { RiskRing, PredictionProgressRing } from "@/components/forecast/RiskRing";
import { usePrediction } from "@/components/providers/PredictionProvider";
import {
  deriveStats,
  deriveHourlyBreakdown,
  actionItems,
  bestTimeOutside,
  airQualityInfo,
  tomorrowComparison,
  dailyTip,
} from "@/lib/deriveStats";
import { RISK_LABEL, RISK_SUMMARY } from "@/lib/riskStyles";
import type { RiskLevel } from "@/lib/types";

const RISK_HEX: Record<RiskLevel, string> = {
  low: "#6FCF97",
  moderate: "#F2C14E",
  high: "#F0883E",
  severe: "#E5533B",
};

const BAR_WORD: Record<RiskLevel, string> = {
  low: "Clear",
  moderate: "Light",
  high: "Dusty",
  severe: "Dusty",
};

const ACTION_ICON = { home: Home, droplet: Droplet, shield: Shield, car: Car };
const ACTION_TINT_BG: Record<RiskLevel, string> = {
  low: "rgba(111,207,151,.16)",
  moderate: "rgba(242,193,78,.16)",
  high: "rgba(240,136,62,.16)",
  severe: "rgba(229,83,59,.16)",
};

const TREND_COPY = {
  worse: { title: "Heads up — tomorrow looks worse", icon: TrendingUp, tint: "high" as RiskLevel },
  better: { title: "Good news — tomorrow looks better", icon: TrendingDown, tint: "low" as RiskLevel },
  similar: { title: "Tomorrow looks about the same", icon: Minus, tint: "moderate" as RiskLevel },
};

export default function TodayPage() {
  const { prediction, progressive, week, switching, switchProgress, error } = usePrediction();

  const today = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  return (
    <DustySky glow="right" scanlines>
      <div className="flex flex-1 flex-col gap-4 px-[18px] pt-1">
        <div className="flex items-center justify-between">
          <LocationPill />
          <div className="flex items-center gap-2.5">
            <Link
              href="/notifications"
              className="relative flex size-[38px] items-center justify-center rounded-[13px] border border-border bg-card backdrop-blur-xl"
            >
              <Bell className="size-[18px] text-sd-strong" />
              <span
                className="absolute right-[9px] top-[9px] size-[7px] rounded-full"
                style={{ background: "#E5533B" }}
              />
            </Link>
            <Link
              href="/settings"
              className="flex size-[38px] items-center justify-center rounded-[13px] border border-border bg-card backdrop-blur-xl"
            >
              <Settings className="size-[18px] text-sd-strong" />
            </Link>
          </div>
        </div>
        <p className="sky-text -mt-2 text-xs font-semibold" style={{ color: "#E9E2D4" }}>
          {today} &middot; updated just now
        </p>

        {error && !prediction && (
          <Card className="items-center gap-1 p-5 text-center">
            <p className="text-sm font-medium text-sd-strong">Couldn&apos;t reach the forecast service</p>
            <p className="text-xs text-sd-muted">Make sure the backend is running, or try again shortly.</p>
          </Card>
        )}

        {!prediction && !error && (
          <>
            <Card className="gap-4 rounded-[28px] border-[rgba(255,255,255,.16)] p-5">
              <div className="flex items-center justify-between">
                <div className="flex flex-col gap-2">
                  <Skeleton className="h-3 w-24" />
                  <Skeleton className="h-9 w-28" />
                </div>
                <Skeleton className="size-[104px] rounded-full" />
              </div>
              <Skeleton className="h-4 w-full" />
            </Card>
            <div className="grid grid-cols-2 gap-3">
              {[0, 1, 2, 3].map((i) => (
                <Card key={i} className="items-center gap-2 rounded-[20px] p-4">
                  <Skeleton className="size-5 rounded-full" />
                  <Skeleton className="h-4 w-10" />
                  <Skeleton className="h-2.5 w-14" />
                </Card>
              ))}
            </div>
            <Card className="gap-0 px-4 pb-3 pt-3.5">
              <Skeleton className="mb-4 h-3.5 w-28" />
              <div className="flex items-end justify-between">
                {[24, 40, 52, 44, 30, 20].map((h, i) => (
                  <div key={i} className="flex flex-col items-center gap-2">
                    <Skeleton className="h-3 w-4" />
                    <Skeleton className="w-[9px] rounded-[6px]" style={{ height: h }} />
                    <Skeleton className="h-2.5 w-6" />
                  </div>
                ))}
              </div>
            </Card>
          </>
        )}

        {prediction && (
          <>
            <Card className="gap-0 rounded-[28px] border-[rgba(255,255,255,.16)] p-5 shadow-[0_14px_34px_rgba(0,0,0,0.28),inset_0_1px_0_rgba(255,255,255,0.12)]">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.02em] text-sd-label">
                    Dust risk today
                  </p>
                  <p
                    className="mt-2 text-[38px] font-extrabold leading-[1.05]"
                    style={{ color: RISK_HEX[prediction.risk] }}
                  >
                    {RISK_LABEL[prediction.risk]}
                  </p>
                </div>
                {switching ? (
                  <PredictionProgressRing progress={switchProgress} size={104} valueSize={26} />
                ) : (
                  <RiskRing probability={prediction.probability} risk={prediction.risk} size={104} valueSize={26} />
                )}
              </div>
              <p className="mt-3.5 text-sm font-medium leading-[1.5] text-sd-primary">
                {RISK_SUMMARY[prediction.risk]}
              </p>
            </Card>

            <div className="grid grid-cols-2 gap-3">
              {(() => {
                const stats = deriveStats(prediction.probability);
                const soilMoisturePct = progressive
                  ? Math.round(progressive.surfaceData.soilMoisture * 100)
                  : null;
                return (
                  <>
                    <StatChip icon={Eye} value={`${stats.visibilityKm} km`} label="Visibility" />
                    <StatChip icon={Wind} value={`${stats.windKmh} km/h`} label="Wind" />
                    <StatChip icon={Sparkles} value={`${stats.airIndex}`} label="Air (dust)" iconColor="#F0883E" />
                    <StatChip
                      icon={Droplets}
                      value={soilMoisturePct !== null ? `${soilMoisturePct}%` : "—"}
                      label="Soil moisture"
                      iconColor="#6FA8DC"
                    />
                  </>
                );
              })()}
            </div>

            {(() => {
              const hourly = deriveHourlyBreakdown(prediction.probability);
              const best = bestTimeOutside(hourly);
              return (
                <Card
                  className="flex-row items-center gap-3 rounded-[18px] p-4"
                  style={{ background: "linear-gradient(135deg,rgba(111,207,151,.22),rgba(20,26,34,.4))" }}
                >
                  <span
                    className="flex size-9 shrink-0 items-center justify-center rounded-full"
                    style={{ background: "rgba(111,207,151,.22)" }}
                  >
                    <Clock className="size-[18px]" style={{ color: "#6FCF97" }} />
                  </span>
                  <div>
                    <p className="text-[13px] font-bold text-sd-strong">Best time to be outside</p>
                    <p className="mt-1 text-xs font-medium text-sd-secondary">
                      Dust chance is lowest in the {best.phrase}.
                    </p>
                  </div>
                </Card>
              );
            })()}

            <Card className="gap-0 px-4 pb-3 pt-3.5">
              <p className="mb-4 text-[13px] font-bold text-sd-primary">Through the day</p>
              <div className="flex items-end justify-between">
                {deriveHourlyBreakdown(prediction.probability).map((hour) => (
                  <div key={hour.label} className="flex flex-col items-center gap-2">
                    <span className="text-[11px] font-semibold text-sd-muted">{hour.label}</span>
                    <span
                      className="w-[9px] rounded-[6px]"
                      style={{
                        height: 18 + hour.probability * 34,
                        background: RISK_HEX[hour.risk],
                      }}
                    />
                    <span
                      className="text-[10px] font-bold"
                      style={{ color: hour.risk === "high" || hour.risk === "severe" ? "#F0C48A" : "#DCE4EB" }}
                    >
                      {BAR_WORD[hour.risk]}
                    </span>
                  </div>
                ))}
              </div>
            </Card>

            {(() => {
              const stats = deriveStats(prediction.probability);
              const air = airQualityInfo(stats.airIndex);
              return (
                <Card className="gap-3 p-5">
                  <div className="flex items-center justify-between">
                    <p className="flex items-center gap-2 text-[13px] font-bold text-sd-primary">
                      <Sparkles className="size-4 text-[#F0883E]" />
                      Air &amp; breathing
                    </p>
                    <span className="text-[13px] font-extrabold text-sd-strong">{air.label}</span>
                  </div>
                  <div
                    className="relative h-2 w-full rounded-full"
                    style={{ background: "linear-gradient(90deg,#6FCF97,#F2C14E,#F0883E,#E5533B)" }}
                  >
                    <span
                      className="absolute top-1/2 size-3.5 -translate-y-1/2 -translate-x-1/2 rounded-full border-2 border-white shadow-[0_2px_6px_rgba(0,0,0,.4)]"
                      style={{ left: `${air.position * 100}%`, background: "#20272e" }}
                    />
                  </div>
                  <p className="text-xs font-medium leading-[1.5] text-sd-secondary">{air.description}</p>
                </Card>
              );
            })()}

            <Card className="gap-3 p-5">
              <p className="text-[13px] font-bold text-sd-primary">What to do today</p>
              <div className="flex flex-col gap-3.5">
                {actionItems(prediction.risk).map((item, i) => {
                  const Icon = ACTION_ICON[item.icon];
                  return (
                    <div key={i} className="flex items-center gap-3">
                      <span
                        className="flex size-[22px] shrink-0 items-center justify-center rounded-[8px]"
                        style={{ background: ACTION_TINT_BG[item.tint] }}
                      >
                        <Icon className="size-[13px]" style={{ color: RISK_HEX[item.tint] }} />
                      </span>
                      <span className="text-[13px] font-medium text-sd-primary">{item.text}</span>
                    </div>
                  );
                })}
              </div>
            </Card>

            {week &&
              week.days.length > 1 &&
              (() => {
                const tomorrow = week.days[1];
                const trend = tomorrowComparison(prediction.probability, tomorrow.probability);
                const copy = TREND_COPY[trend];
                const TrendIcon = copy.icon;
                return (
                  <Card className="gap-3 p-5">
                    <p className="flex items-center gap-2 text-[13px] font-bold text-sd-primary">
                      <TrendIcon className="size-4" style={{ color: RISK_HEX[copy.tint] }} />
                      {copy.title}
                    </p>
                    <div className="flex items-center gap-3">
                      <span
                        className="flex size-11 shrink-0 items-center justify-center rounded-full text-sm font-extrabold"
                        style={{ background: `${RISK_HEX[tomorrow.risk]}29`, color: RISK_HEX[tomorrow.risk] }}
                      >
                        {(tomorrow.probability * 100).toFixed(0)}%
                      </span>
                      <p className="text-xs font-medium leading-[1.5] text-sd-secondary">
                        Tomorrow is looking{" "}
                        <span style={{ color: RISK_HEX[tomorrow.risk] }} className="font-bold">
                          {RISK_LABEL[tomorrow.risk].toLowerCase()}
                        </span>{" "}
                        for dust — {RISK_SUMMARY[tomorrow.risk].toLowerCase()}
                      </p>
                    </div>
                  </Card>
                );
              })()}

            <Card className="gap-3 p-5">
              <div className="flex items-center justify-between">
                <p className="text-[13px] font-bold text-sd-primary">Next 3 days</p>
                <Link href="/location" className="flex items-center gap-0.5 text-xs font-bold text-[#F2C14E]">
                  See my area <ChevronRight className="size-3.5" />
                </Link>
              </div>
              <div className="flex gap-3">
                {week ? (
                  week.days.slice(0, 3).map((day) => (
                    <div
                      key={day.date}
                      className="flex flex-1 flex-col items-center gap-1.5 rounded-[16px] p-3"
                      style={{ background: "rgba(12,16,20,.4)" }}
                    >
                      <span className="text-[11px] font-semibold text-sd-muted">
                        {new Date(day.date).toLocaleDateString(undefined, { weekday: "short" })}
                      </span>
                      <span className="text-sm font-extrabold" style={{ color: RISK_HEX[day.risk] }}>
                        {(day.probability * 100).toFixed(0)}%
                      </span>
                      <span className="text-[10px] font-semibold text-sd-secondary">
                        {RISK_LABEL[day.risk]}
                      </span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-sd-muted">Waiting on the next forecast update...</p>
                )}
              </div>
            </Card>

            {week && week.days.length >= 4 && (
              <Card className="gap-4 p-5">
                <p className="text-[13px] font-bold text-sd-primary">This week at a glance</p>
                <div className="flex items-end justify-between">
                  {week.days.map((day) => (
                    <div key={day.date} className="flex flex-col items-center gap-2">
                      <span className="text-[10px] font-bold text-sd-strong">
                        {(day.probability * 100).toFixed(0)}
                      </span>
                      <span
                        className="w-[9px] rounded-[6px]"
                        style={{ height: 18 + day.probability * 34, background: RISK_HEX[day.risk] }}
                      />
                      <span className="text-[10px] font-semibold text-sd-muted">
                        {new Date(day.date).toLocaleDateString(undefined, { weekday: "short" }).slice(0, 2)}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            <Card
              className="flex-row items-start gap-3 rounded-[18px] p-4"
              style={{ background: "linear-gradient(135deg,rgba(242,193,78,.2),rgba(20,26,34,.4))" }}
            >
              <span
                className="flex size-9 shrink-0 items-center justify-center rounded-full"
                style={{ background: "rgba(242,193,78,.22)" }}
              >
                <Lightbulb className="size-[18px]" style={{ color: "#F2C14E" }} />
              </span>
              <div>
                <p className="text-[13px] font-bold text-sd-strong">Did you know?</p>
                <p className="mt-1 text-xs font-medium leading-[1.5] text-sd-secondary">{dailyTip()}</p>
              </div>
            </Card>
          </>
        )}
      </div>
    </DustySky>
  );
}

function StatChip({
  icon: Icon,
  label,
  value,
  iconColor,
}: {
  icon: typeof Eye;
  label: string;
  value: string;
  iconColor?: string;
}) {
  return (
    <Card className="items-center gap-1.5 rounded-[20px] p-4 text-center">
      <Icon className="size-5" style={{ color: iconColor ?? "#DCE4EB" }} />
      <span className="text-[17px] font-extrabold text-sd-strong">{value}</span>
      <span className="text-[10px] font-semibold text-sd-muted">{label}</span>
    </Card>
  );
}
