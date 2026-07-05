import { TrendingUp, TrendingDown, Minus, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Trend } from "@/lib/types";

const TREND_META: Record<Trend, { label: string; icon: typeof TrendingUp; className: string }> = {
  increasing: { label: "Increasing", icon: TrendingUp, className: "text-risk-severe" },
  decreasing: { label: "Decreasing", icon: TrendingDown, className: "text-risk-low" },
  stable: { label: "Stable", icon: Minus, className: "text-muted-foreground" },
  new: { label: "New", icon: Sparkles, className: "text-primary" },
};

export function TrendIndicator({ trend }: { trend: Trend }) {
  const meta = TREND_META[trend];
  const Icon = meta.icon;
  return (
    <span className={cn("inline-flex items-center gap-1 text-sm font-medium", meta.className)}>
      <Icon className="size-4" />
      {meta.label}
    </span>
  );
}
