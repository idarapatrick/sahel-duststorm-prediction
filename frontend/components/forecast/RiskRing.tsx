import type { RiskLevel } from "@/lib/types";

const RISK_STROKE: Record<RiskLevel, string> = {
  low: "var(--risk-low)",
  moderate: "var(--risk-moderate)",
  high: "var(--risk-high)",
  severe: "var(--risk-severe)",
};

export function RiskRing({
  probability,
  risk,
  size = 90,
  valueSize = 23,
}: {
  probability: number;
  risk: RiskLevel;
  size?: number;
  valueSize?: number;
}) {
  const stroke = 11;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - probability);

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,.15)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={RISK_STROKE[risk]}
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div
        className="absolute flex flex-col items-center justify-center rounded-full"
        style={{ inset: 11, background: "rgba(16,21,26,.72)" }}
      >
        <span
          className="font-extrabold leading-none text-sd-strong"
          style={{ fontSize: valueSize }}
        >
          {(probability * 100).toFixed(0)}
          <span className="text-xs">%</span>
        </span>
        <span className="mt-[3px] text-[9px] font-bold uppercase tracking-[0.09em] text-sd-label">
          chance
        </span>
      </div>
    </div>
  );
}

/**
 * Drop-in replacement for RiskRing while a new location's prediction is being
 * fetched -- same footprint, but the ring tracks fetch progress (not dust
 * risk) so the hero card never goes blank mid-switch.
 */
export function PredictionProgressRing({
  progress,
  size = 90,
  valueSize = 23,
}: {
  progress: number;
  size?: number;
  valueSize?: number;
}) {
  const stroke = 11;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - progress / 100);

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,.15)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#F2C14E"
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 150ms linear" }}
        />
      </svg>
      <div
        className="absolute flex flex-col items-center justify-center rounded-full"
        style={{ inset: 11, background: "rgba(16,21,26,.72)" }}
      >
        <span className="font-extrabold leading-none text-sd-strong" style={{ fontSize: valueSize }}>
          {Math.round(progress)}
          <span className="text-xs">%</span>
        </span>
        <span className="mt-[3px] text-[9px] font-bold uppercase tracking-[0.09em] text-sd-label">
          updating
        </span>
      </div>
    </div>
  );
}
