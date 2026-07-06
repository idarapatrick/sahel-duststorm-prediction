"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { DustySky } from "@/components/layout/DustySky";
import { ALERT_STATUS_LABEL } from "@/lib/riskStyles";
import { getActiveAlerts } from "@/lib/api";
import type { AlertLevel, TrackedAlert } from "@/lib/types";
import { Loader2, Bell } from "lucide-react";

interface NotificationEntry {
  key: string;
  locationName: string;
  timestamp: string;
  level: TrackedAlert["currentAlert"]["level"];
  probability: number;
}

const ALERT_HEX: Record<AlertLevel, string> = {
  clear: "#6FCF97",
  watch: "#F2C14E",
  warning: "#F0883E",
  alert: "#E5533B",
};

export default function NotificationsPage() {
  const [entries, setEntries] = useState<NotificationEntry[] | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    getActiveAlerts().then((data) => {
      if (!data) {
        setStatus("error");
        return;
      }
      const flattened = data.predictions.flatMap((alert) =>
        alert.updates
          .filter((u) => u.alertLevel !== "clear")
          .map((u) => ({
            key: `${alert.lat}-${alert.lon}-${u.timestamp}`,
            locationName: alert.locationName,
            timestamp: u.timestamp,
            level: u.alertLevel,
            probability: u.probability,
          }))
      );
      flattened.sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1));
      setEntries(flattened);
      setStatus("ready");
    });
  }, []);

  return (
    <DustySky glow="right">
      <div className="flex flex-1 flex-col gap-4 px-[18px] pt-2">
        <p className="sky-text text-2xl font-extrabold text-sd-strong">Notifications</p>

        {status === "loading" && (
          <div className="flex justify-center py-10 text-sd-muted">
            <Loader2 className="size-6 animate-spin" />
          </div>
        )}

        {status === "error" && (
          <p className="sky-text text-xs text-sd-muted">Couldn&apos;t reach the alert service.</p>
        )}

        {status === "ready" && entries && entries.length === 0 && (
          <div className="sky-text flex flex-1 flex-col items-center justify-center gap-2 text-center text-sd-muted">
            <Bell className="sky-icon size-8" />
            <p className="text-sm font-semibold text-sd-primary">No notifications yet</p>
            <p className="text-xs">You&apos;ll see updates here when tracked towns change risk level.</p>
          </div>
        )}

        {status === "ready" && entries && entries.length > 0 && (
          <div className="flex flex-col gap-2">
            {entries.map((entry) => (
              <Card key={entry.key} className="flex-row items-center gap-3 p-4">
                <div
                  className="flex size-9 shrink-0 items-center justify-center rounded-full"
                  style={{ background: `${ALERT_HEX[entry.level]}29` }}
                >
                  <Bell className="size-4" style={{ color: ALERT_HEX[entry.level] }} />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-bold text-sd-strong">
                    {entry.locationName}: {ALERT_STATUS_LABEL[entry.level]}
                  </p>
                  <p className="text-xs text-sd-muted">{new Date(entry.timestamp).toLocaleString()}</p>
                </div>
                <span
                  className="rounded-[10px] px-[9px] py-1 text-[11px] font-extrabold"
                  style={{ color: "#20272e", background: ALERT_HEX[entry.level] }}
                >
                  {(entry.probability * 100).toFixed(0)}%
                </span>
              </Card>
            ))}
          </div>
        )}
      </div>
    </DustySky>
  );
}
