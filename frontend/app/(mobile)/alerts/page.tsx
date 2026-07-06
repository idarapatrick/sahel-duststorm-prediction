"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Cloud, Phone, ShieldCheck, Trash2, Wind } from "lucide-react";
import { Card } from "@/components/ui/card";
import { DustySky } from "@/components/layout/DustySky";
import { LocationPill } from "@/components/forecast/LocationPill";
import { useSelectedLocation } from "@/components/providers/LocationProvider";
import { getActiveAlerts } from "@/lib/api";
import { getLinkedPhone } from "@/lib/phoneLink";
import { ALERT_TERSE_LABEL } from "@/lib/riskStyles";
import type { AlertLevel, AlertSubscription, TrackedAlert } from "@/lib/types";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const STORAGE_KEY = "saheldust:subscriptions";
const THRESHOLDS: AlertLevel[] = ["watch", "warning", "alert"];

const ALERT_HEX: Record<AlertLevel, string> = {
  clear: "#6FCF97",
  watch: "#F2C14E",
  warning: "#F0883E",
  alert: "#E5533B",
};

const ALERT_ICON = { clear: Cloud, watch: Cloud, warning: Wind, alert: Wind };

function loadSubscriptions(): AlertSubscription[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function saveSubscriptions(subs: AlertSubscription[]) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(subs));
}

export default function AlertsPage() {
  const { location } = useSelectedLocation();
  const [linkedPhone, setLinkedPhone] = useState<string | null>(null);
  const [threshold, setThreshold] = useState<AlertLevel>("warning");
  const [subscriptions, setSubscriptions] = useState<AlertSubscription[]>([]);

  const [active, setActive] = useState<TrackedAlert[] | null>(null);
  const [activeStatus, setActiveStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    setSubscriptions(loadSubscriptions());
    setLinkedPhone(getLinkedPhone());
    getActiveAlerts().then((data) => {
      setActive(data?.predictions ?? null);
      setActiveStatus(data ? "ready" : "error");
    });
  }, []);

  function handleSubscribe() {
    if (!linkedPhone) return;
    const next = [
      ...subscriptions,
      { phone: linkedPhone, lat: location.lat, lon: location.lon, locationName: location.name, threshold },
    ];
    setSubscriptions(next);
    saveSubscriptions(next);
    toast.success(`Alerts on for ${location.name}`);
  }

  function handleRemove(index: number) {
    const next = subscriptions.filter((_, i) => i !== index);
    setSubscriptions(next);
    saveSubscriptions(next);
  }

  const activeAlerts = active?.filter((a) => a.currentAlert.level !== "clear") ?? [];
  const livePulse = activeAlerts.length > 0;

  return (
    <DustySky glow="left">
      <div className="flex flex-1 flex-col gap-4 px-[18px] pt-2">
        <div className="sky-text">
          <p className="text-2xl font-extrabold text-sd-strong">Alerts</p>
          <p className="mt-[3px] text-[13px] font-medium text-sd-primary">
            Get a heads-up before dust reaches you.
          </p>
        </div>

        <Card
          className="gap-4 rounded-[24px] border-[rgba(255,255,255,.2)] p-5 shadow-[0_14px_34px_rgba(0,0,0,0.24)]"
        >
          <LocationPill variant="field" />

          {linkedPhone ? (
            <div
              className="flex items-center justify-between gap-2 rounded-[14px] border px-[13px] py-3"
              style={{ background: "rgba(12,16,20,.62)", borderColor: "rgba(255,255,255,.1)" }}
            >
              <span className="flex items-center gap-2 text-sm font-medium text-sd-primary">
                <ShieldCheck className="size-4 shrink-0 text-[#6FCF97]" />
                {linkedPhone}
              </span>
              <Link href="/link-phone?redirect=/alerts" className="shrink-0 text-xs font-bold text-[#F2C14E]">
                Change
              </Link>
            </div>
          ) : (
            <div
              className="flex items-center gap-[10px] rounded-[14px] border px-[13px] py-3"
              style={{ background: "rgba(12,16,20,.62)", borderColor: "rgba(255,255,255,.1)" }}
            >
              <Phone className="size-4 shrink-0 text-sd-muted" />
              <Link
                href="/link-phone?redirect=/alerts"
                className="flex-1 text-sm font-semibold text-[#F2C14E]"
              >
                Link your phone number
              </Link>
            </div>
          )}

          <div>
            <p className="mb-2 text-xs font-bold text-sd-label">Tell me when it reaches</p>
            <div className="flex gap-2">
              {THRESHOLDS.map((level) => (
                <button
                  key={level}
                  onClick={() => setThreshold(level)}
                  className="flex-1 rounded-xl py-[9px] text-xs font-bold transition-colors"
                  style={
                    threshold === level
                      ? { color: "#20272e", background: "#F0883E", border: "1px solid #F0883E" }
                      : {
                          color: "#B9C4CE",
                          background: "rgba(12,16,20,.58)",
                          border: "1px solid rgba(255,255,255,.1)",
                        }
                  }
                >
                  {ALERT_TERSE_LABEL[level]}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={handleSubscribe}
            disabled={!linkedPhone}
            className="rounded-[14px] py-[13px] text-sm font-extrabold text-[#20272e] shadow-[0_8px_20px_rgba(240,136,62,0.3)] disabled:opacity-40"
            style={{ background: "linear-gradient(90deg,#F2C14E,#F0883E)" }}
          >
            Turn on alerts
          </button>
          <p className="text-center text-[11px] font-medium leading-[1.5] text-sd-muted">
            Saved on this phone. Free text-message alerts are coming soon.
          </p>
        </Card>

        {subscriptions.length > 0 && (
          <div className="mt-0.5">
            <p className="mb-2 text-[13px] font-bold text-sd-primary">Your alerts</p>
            <div className="flex flex-col gap-2">
              {subscriptions.map((sub, i) => (
                <Card key={i} className="flex-row items-center justify-between gap-3 rounded-[18px] p-[16px_18px]">
                  <div>
                    <p className="text-sm font-bold text-sd-strong">{sub.locationName}</p>
                    <p className="mt-[2px] text-[11px] font-medium text-sd-muted">
                      {sub.phone} &middot; at {ALERT_TERSE_LABEL[sub.threshold]}
                    </p>
                  </div>
                  <button onClick={() => handleRemove(i)} aria-label="Remove alert">
                    <Trash2 className="size-[17px] text-sd-faint" />
                  </button>
                </Card>
              ))}
            </div>
          </div>
        )}

        <div className="mt-0.5">
          <div className="mb-2 flex items-center gap-2">
            <p className="text-[13px] font-bold text-sd-primary">Active now</p>
            {livePulse && (
              <span
                className="size-[7px] rounded-full"
                style={{ background: "#E5533B", animation: "livepulse 1.6s ease-in-out infinite" }}
              />
            )}
          </div>

          {activeStatus === "loading" && <p className="text-xs text-sd-muted">Checking...</p>}
          {activeStatus === "error" && (
            <p className="text-xs text-sd-muted">Couldn&apos;t reach the alert service.</p>
          )}
          {activeStatus === "ready" && activeAlerts.length === 0 && (
            <p className="text-xs text-sd-muted">No active dust risks right now.</p>
          )}

          {activeStatus === "ready" && activeAlerts.length > 0 && (
            <div className="flex flex-col gap-2">
              {activeAlerts.map((alert) => {
                const Icon = ALERT_ICON[alert.currentAlert.level];
                return (
                  <Card
                    key={`${alert.lat}-${alert.lon}-${alert.targetDate}`}
                    className="flex-row items-center justify-between rounded-[18px] p-[16px_18px]"
                  >
                    <div className="flex items-center gap-[11px]">
                      <span
                        className={cn("flex size-[34px] items-center justify-center rounded-[11px]")}
                        style={{ background: `${ALERT_HEX[alert.currentAlert.level]}29` }}
                      >
                        <Icon className="size-[18px]" style={{ color: ALERT_HEX[alert.currentAlert.level] }} />
                      </span>
                      <div>
                        <p className="text-sm font-bold text-sd-strong">{alert.locationName}</p>
                        <p className="mt-[1px] text-[11px] font-medium text-sd-muted">
                          Watching for {alert.targetDate}
                        </p>
                      </div>
                    </div>
                    <span
                      className="rounded-[10px] px-[9px] py-1 text-[11px] font-extrabold"
                      style={{ color: "#20272e", background: ALERT_HEX[alert.currentAlert.level] }}
                    >
                      {ALERT_TERSE_LABEL[alert.currentAlert.level]}
                    </span>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </DustySky>
  );
}
