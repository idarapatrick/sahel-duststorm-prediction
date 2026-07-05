import { cn } from "@/lib/utils";
import { RISK_BADGE_CLASS, RISK_LABEL } from "@/lib/riskStyles";
import type { RiskLevel } from "@/lib/types";

export function RiskIndicator({
  risk,
  probability,
  size = "lg",
}: {
  risk: RiskLevel;
  probability?: number;
  size?: "sm" | "lg";
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-1 rounded-3xl border text-center",
        RISK_BADGE_CLASS[risk],
        size === "lg" ? "px-8 py-6" : "px-4 py-3"
      )}
    >
      <span className={cn("font-semibold", size === "lg" ? "text-2xl" : "text-base")}>
        {RISK_LABEL[risk]}
      </span>
      {probability !== undefined && (
        <span className="font-mono text-sm text-muted-foreground">
          {(probability * 100).toFixed(0)}% probability
        </span>
      )}
    </div>
  );
}
