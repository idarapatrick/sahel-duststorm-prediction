"use client";

import Link from "next/link";
import { ChevronLeft, Droplet, Home, Shield, Users, Wind } from "lucide-react";
import { Card } from "@/components/ui/card";
import { DustySky } from "@/components/layout/DustySky";
import { KNOWN_LOCATIONS } from "@/lib/locations";

const SHOWN_TOWNS = KNOWN_LOCATIONS.slice(0, 9);
const MORE_COUNT = KNOWN_LOCATIONS.length - SHOWN_TOWNS.length;

const SAFETY_TIPS = [
  { icon: Shield, tint: "rgba(240,136,62,.16)", color: "#F0883E", text: "Cover your nose and mouth outside" },
  { icon: Home, tint: "rgba(111,207,151,.16)", color: "#7FD9A6", text: "Close windows and doors" },
  { icon: Droplet, tint: "rgba(242,193,78,.16)", color: "#F2C14E", text: "Cover drinking water and food" },
  { icon: Users, tint: "rgba(229,83,59,.16)", color: "#E5533B", text: "Keep children and elderly indoors" },
];

export default function AboutPage() {
  return (
    <DustySky glow="left">
      <div className="flex flex-1 flex-col gap-4 px-[18px] pt-2">
        <Link href="/settings" className="flex items-center gap-[10px]">
          <span className="flex size-[34px] items-center justify-center rounded-[11px] border border-border bg-card backdrop-blur-xl">
            <ChevronLeft className="size-[18px] text-sd-strong" />
          </span>
          <span className="sky-text text-[15px] font-semibold text-sd-secondary">Settings</span>
        </Link>

        <div className="mt-1 flex items-center gap-3">
          <div
            className="flex size-[46px] items-center justify-center rounded-[15px] shadow-[0_8px_20px_rgba(229,83,59,0.32)]"
            style={{ background: "linear-gradient(150deg,#F2C14E,#E5533B)" }}
          >
            <Wind className="size-6 text-[#20272e]" />
          </div>
          <div className="sky-text">
            <p className="text-[22px] font-extrabold text-sd-strong">SahelDust</p>
            <p className="mt-[1px] text-[13px] font-medium text-sd-primary">
              Simple dust-storm warnings for the Sahel.
            </p>
          </div>
        </div>

        <Card className="gap-2 rounded-[22px] border-[rgba(255,255,255,.2)] p-5 shadow-[0_14px_34px_rgba(0,0,0,0.24)]">
          <p className="text-[13px] font-bold text-sd-primary">What this app does</p>
          <p className="text-[13px] font-medium leading-[1.5] text-sd-secondary">
            Tells you when dust and sandstorms are heading for your town, how strong they may be,
            and what to do to stay safe.
          </p>
        </Card>

        <Card className="gap-2 p-5">
          <p className="text-[13px] font-bold text-sd-primary">How we make the forecast</p>
          <p className="text-[13px] font-medium leading-[1.5] text-sd-secondary">
            We read live weather and satellite views of the land and sky to work out the chance
            of dust. It keeps updating as the day gets closer, so it grows more reliable.
          </p>
        </Card>

        <Card className="gap-3.5 p-5">
          <p className="text-[13px] font-bold text-sd-primary">Towns we cover</p>
          <div className="flex flex-wrap gap-[7px]">
            {SHOWN_TOWNS.map((town) => (
              <span
                key={town.name}
                className="rounded-[11px] border px-[10px] py-[5px] text-[11px] font-semibold text-sd-primary"
                style={{ background: "rgba(12,16,20,.58)", borderColor: "rgba(255,255,255,.1)" }}
              >
                {town.name}
              </span>
            ))}
            {MORE_COUNT > 0 && (
              <span
                className="rounded-[11px] border px-[10px] py-[5px] text-[11px] font-semibold text-sd-faint"
                style={{ background: "rgba(12,16,20,.58)", borderColor: "rgba(255,255,255,.1)" }}
              >
                +{MORE_COUNT} more
              </span>
            )}
          </div>
        </Card>

        <Card className="gap-3.5 p-5">
          <p className="text-[13px] font-bold text-sd-primary">Staying safe in a storm</p>
          <div className="flex flex-col gap-2">
            {SAFETY_TIPS.map((tip, i) => (
              <div key={i} className="flex items-center gap-2.5">
                <span
                  className="flex size-[22px] shrink-0 items-center justify-center rounded-[8px]"
                  style={{ background: tip.tint }}
                >
                  <tip.icon className="size-[13px]" style={{ color: tip.color }} />
                </span>
                <span className="text-[13px] font-medium text-sd-primary">{tip.text}</span>
              </div>
            ))}
          </div>
        </Card>

        <p className="mt-1 pb-4 text-center text-[11px] font-medium text-sd-faint">
          Built for Sahel communities &middot; v1.0
        </p>
      </div>
    </DustySky>
  );
}
