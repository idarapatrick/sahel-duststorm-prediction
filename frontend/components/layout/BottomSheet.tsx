import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { RISK_BADGE_CLASS } from "@/lib/riskStyles";
import type { GridPrediction } from "@/lib/types";

export function BottomSheet({ cells }: { cells: GridPrediction[] }) {
  const severeCount = cells.filter((c) => c.severity === "severe").length;
  const moderateCount = cells.filter(
    (c) => c.severity === "moderate" || c.severity === "high"
  ).length;
  const worst = cells.reduce((a, b) => (b.probability > a.probability ? b : a), cells[0]);

  return (
    <div className="absolute inset-x-0 bottom-0 z-[400] rounded-t-3xl border-t border-border/60 bg-white/85 px-5 pt-3 pb-5 shadow-[0_-8px_24px_rgba(0,0,0,0.06)] backdrop-blur-lg">
      <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-muted-foreground/30" />
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">Sahel region summary</p>
          <p className="text-lg font-semibold">
            {severeCount} severe &middot; {moderateCount} elevated zones
          </p>
        </div>
        <Badge variant="outline" className={cn("capitalize", RISK_BADGE_CLASS[worst.severity])}>
          Peak: {worst.severity}
        </Badge>
      </div>
    </div>
  );
}
