import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { RISK_BADGE_CLASS } from "@/lib/riskStyles";
import type { ForecastDay } from "@/lib/types";

export function ForecastCard({
  forecast,
  label,
}: {
  forecast: ForecastDay;
  label: string;
}) {
  return (
    <Card className="flex min-w-[132px] flex-col items-center gap-2 border-border/60 bg-white/80 px-4 py-5 text-center shadow-sm backdrop-blur">
      <span className="text-sm font-medium text-muted-foreground">{label}</span>
      <Badge
        variant="outline"
        className={cn("capitalize", RISK_BADGE_CLASS[forecast.risk])}
      >
        {forecast.risk}
      </Badge>
      <span className="font-mono text-lg font-semibold">
        {(forecast.probability * 100).toFixed(0)}%
      </span>
    </Card>
  );
}
