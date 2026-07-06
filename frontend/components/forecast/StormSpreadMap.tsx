"use client";

import { useState } from "react";
import { Navigation, ArrowDownLeft, Info } from "lucide-react";

type TownStatus = "clear" | "watch" | "moderate" | "high" | "severe";

interface Step {
  label: string;
  cx: number;
  cy: number;
  w: number;
  h: number;
  core: number;
  towns: { Agadez: TownStatus; Niamey: TownStatus; Kano: TownStatus };
  caption: string;
}

// Illustrative sample data matching the design reference -- in production,
// drive cloud position/size from a wind-drift forecast series and each
// town's status from its per-step chance. The scrub interaction stays the same.
const STEPS: Step[] = [
  {
    label: "Now",
    cx: 68,
    cy: 26,
    w: 160,
    h: 132,
    core: 74,
    towns: { Agadez: "severe", Niamey: "clear", Kano: "clear" },
    caption: "Dust is over Agadez right now. Niamey and Kano are still clear.",
  },
  {
    label: "+6h",
    cx: 55,
    cy: 39,
    w: 214,
    h: 168,
    core: 92,
    towns: { Agadez: "high", Niamey: "watch", Kano: "clear" },
    caption: "The cloud is drifting southwest. Niamey should get ready — Kano stays clear.",
  },
  {
    label: "+12h",
    cx: 41,
    cy: 50,
    w: 268,
    h: 208,
    core: 112,
    towns: { Agadez: "moderate", Niamey: "high", Kano: "clear" },
    caption: "Dust reaches Niamey. Moving toward Kano keeps you out of the worst of it.",
  },
  {
    label: "+24h",
    cx: 29,
    cy: 58,
    w: 324,
    h: 252,
    core: 132,
    towns: { Agadez: "watch", Niamey: "severe", Kano: "watch" },
    caption: "Niamey is fully in the storm. Areas to the east stay much lighter.",
  },
];

const STATUS_COLOR: Record<TownStatus, string> = {
  clear: "#6FCF97",
  watch: "#F2C14E",
  moderate: "#F2C14E",
  high: "#F0883E",
  severe: "#E5533B",
};

const TOWN_POS = {
  Agadez: { l: 70, t: 24 },
  Niamey: { l: 26, t: 60 },
  Kano: { l: 82, t: 72 },
} as const;

export function StormSpreadMap() {
  const [step, setStep] = useState(1);
  const cur = STEPS[step];

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[13px] font-bold text-sd-primary">How the storm may spread</span>
        <span
          className="inline-flex items-center gap-[5px] rounded-[11px] px-[9px] py-1"
          style={{ background: "rgba(240,136,62,.16)" }}
        >
          <Navigation className="size-3" style={{ color: "#F0883E" }} />
          <span className="text-[10px] font-bold" style={{ color: "#F0C48A" }}>
            Drifting SW
          </span>
        </span>
      </div>

      <div
        className="relative h-[206px] w-full overflow-hidden rounded-2xl"
        style={{
          background:
            "radial-gradient(120% 100% at 30% 20%, rgba(90,110,90,.32), rgba(40,50,44,.5)), linear-gradient(160deg,#3c4a44,#2b3630)",
        }}
      >
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.05) 1px,transparent 1px)",
            backgroundSize: "34px 30px",
          }}
        />
        <div
          className="absolute rounded-full transition-all duration-[550ms] ease-[cubic-bezier(0.4,0,0.2,1)]"
          style={{
            left: `${cur.cx}%`,
            top: `${cur.cy}%`,
            width: cur.w,
            height: cur.h,
            transform: "translate(-50%,-50%)",
            background:
              "radial-gradient(circle, rgba(240,136,62,.6) 0%, rgba(242,193,78,.38) 38%, rgba(229,83,59,.2) 60%, rgba(0,0,0,0) 74%)",
            filter: "blur(7px)",
          }}
        />
        <div
          className="absolute rounded-full transition-all duration-[550ms] ease-[cubic-bezier(0.4,0,0.2,1)]"
          style={{
            left: `${cur.cx}%`,
            top: `${cur.cy}%`,
            width: cur.core,
            height: cur.core,
            transform: "translate(-50%,-50%)",
            background: "radial-gradient(circle, rgba(229,83,59,.5) 0%, rgba(229,83,59,0) 70%)",
            filter: "blur(5px)",
          }}
        />
        <div className="absolute" style={{ left: "66%", top: "22%", transform: "translate(-50%,-50%)" }}>
          <ArrowDownLeft className="size-7" style={{ color: "rgba(255,255,255,.45)" }} />
        </div>
        {(Object.keys(TOWN_POS) as Array<keyof typeof TOWN_POS>).map((name) => {
          const pos = TOWN_POS[name];
          const color = STATUS_COLOR[cur.towns[name]];
          return (
            <div
              key={name}
              className="absolute flex items-center gap-[5px]"
              style={{ left: `${pos.l}%`, top: `${pos.t}%`, transform: "translate(-50%,-50%)" }}
            >
              <span
                className="size-[11px] rounded-full"
                style={{ background: color, boxShadow: `0 0 0 3px rgba(0,0,0,.3), 0 0 10px ${color}` }}
              />
              <span
                className="text-[10px] font-bold text-white"
                style={{ textShadow: "0 1px 3px rgba(0,0,0,.7)" }}
              >
                {name}
              </span>
            </div>
          );
        })}
      </div>

      <div className="mt-3 flex gap-[6px]">
        {STEPS.map((s, i) => (
          <button
            key={s.label}
            onClick={() => setStep(i)}
            className="flex-1 rounded-[11px] py-2 text-[11px] font-extrabold transition-all duration-200"
            style={{
              color: i === step ? "#20272e" : "#B9C4CE",
              background: i === step ? "#F0883E" : "rgba(12,16,20,.58)",
              border: `1px solid ${i === step ? "#F0883E" : "rgba(255,255,255,.1)"}`,
            }}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="mt-3 flex items-start gap-2">
        <Info className="mt-[1px] size-[15px] shrink-0" style={{ color: "#F2C14E" }} />
        <span className="text-xs font-semibold leading-[1.5] text-sd-primary">{cur.caption}</span>
      </div>
    </div>
  );
}
