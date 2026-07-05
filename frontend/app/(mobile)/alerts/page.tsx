"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { LocationSearch } from "@/components/forecast/LocationSearch";
import { ALERT_BADGE_CLASS } from "@/lib/riskStyles";
import { getActiveAlerts } from "@/lib/api";
import { KNOWN_LOCATIONS, type KnownLocation } from "@/lib/locations";
import type { AlertLevel, AlertSubscription, TrackedAlert } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Loader2, Trash2 } from "lucide-react";
import { toast } from "sonner";

const STORAGE_KEY = "saheldust:subscriptions";
const THRESHOLDS: AlertLevel[] = ["watch", "warning", "alert"];

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
  const [location, setLocation] = useState<KnownLocation>(KNOWN_LOCATIONS[0]);
  const [phone, setPhone] = useState("");
  const [threshold, setThreshold] = useState<AlertLevel>("warning");
  const [subscriptions, setSubscriptions] = useState<AlertSubscription[]>([]);

  const [active, setActive] = useState<TrackedAlert[] | null>(null);
  const [activeStatus, setActiveStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    setSubscriptions(loadSubscriptions());
    getActiveAlerts().then((data) => {
      setActive(data?.predictions ?? null);
      setActiveStatus(data ? "ready" : "error");
    });
  }, []);

  function handleSubscribe() {
    if (!phone.trim()) {
      toast.error("Enter a phone number first");
      return;
    }
    const next = [
      ...subscriptions,
      { phone, lat: location.lat, lon: location.lon, locationName: location.name, threshold },
    ];
    setSubscriptions(next);
    saveSubscriptions(next);
    setPhone("");
    toast.success(`Saved alert preference for ${location.name}`);
  }

  function handleRemove(index: number) {
    const next = subscriptions.filter((_, i) => i !== index);
    setSubscriptions(next);
    saveSubscriptions(next);
  }

  return (
    <div className="flex flex-1 flex-col gap-6 px-5 pt-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Alerts</h1>
        <p className="text-sm text-muted-foreground">
          Subscribe to alerts for a location and threshold
        </p>
      </div>

      <Card className="flex flex-col gap-3 border-border/60 bg-white/80 p-4">
        <LocationSearch onSelect={setLocation} placeholder="Choose a location..." />
        <p className="text-xs text-muted-foreground">Selected: {location.name}, {location.country}</p>
        <Input
          type="tel"
          placeholder="Phone number"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
        />
        <Select value={threshold} onValueChange={(v) => setThreshold(v as AlertLevel)}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Alert threshold" />
          </SelectTrigger>
          <SelectContent>
            {THRESHOLDS.map((level) => (
              <SelectItem key={level} value={level} className="capitalize">
                {level}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button onClick={handleSubscribe}>Save preference</Button>
        <p className="text-xs text-muted-foreground">
          Saved on this device only for now. SMS delivery is coming in a later update.
        </p>
      </Card>

      {subscriptions.length > 0 && (
        <Card className="border-border/60 bg-white/80 p-4">
          <p className="mb-3 text-sm font-medium">Your preferences</p>
          <div className="flex flex-col gap-2">
            {subscriptions.map((sub, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <div>
                  <p className="font-medium">{sub.locationName}</p>
                  <p className="text-xs text-muted-foreground">
                    {sub.phone} &middot; threshold: {sub.threshold}
                  </p>
                </div>
                <button onClick={() => handleRemove(i)} aria-label="Remove preference">
                  <Trash2 className="size-4 text-muted-foreground hover:text-risk-severe" />
                </button>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div>
        <p className="mb-3 text-sm font-medium">Active alerts (live)</p>

        {activeStatus === "loading" && (
          <div className="flex justify-center py-6 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
          </div>
        )}

        {activeStatus === "error" && (
          <p className="text-xs text-muted-foreground">Couldn&apos;t reach the alert service.</p>
        )}

        {activeStatus === "ready" && active && active.length === 0 && (
          <p className="text-xs text-muted-foreground">No locations are currently being tracked.</p>
        )}

        {activeStatus === "ready" && active && active.length > 0 && (
          <div className="flex flex-col gap-2">
            {active.map((alert) => (
              <Card
                key={`${alert.lat}-${alert.lon}-${alert.targetDate}`}
                className="flex items-center justify-between border-border/60 bg-white/80 p-3"
              >
                <div>
                  <p className="text-sm font-medium">{alert.locationName}</p>
                  <p className="text-xs text-muted-foreground">Target: {alert.targetDate}</p>
                </div>
                <Badge
                  variant="outline"
                  className={cn("capitalize", ALERT_BADGE_CLASS[alert.currentAlert.level])}
                >
                  {alert.currentAlert.level}
                </Badge>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
