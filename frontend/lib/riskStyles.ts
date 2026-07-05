import type { AlertLevel, RiskLevel } from "./types";

export const RISK_BADGE_CLASS: Record<RiskLevel, string> = {
  low: "bg-risk-low/10 text-risk-low border-risk-low/30",
  moderate: "bg-risk-moderate/10 text-risk-moderate border-risk-moderate/30",
  high: "bg-risk-high/10 text-risk-high border-risk-high/30",
  severe: "bg-risk-severe/10 text-risk-severe border-risk-severe/30",
};

export const RISK_LABEL: Record<RiskLevel, string> = {
  low: "Low Risk",
  moderate: "Moderate Risk",
  high: "High Risk",
  severe: "Severe Risk",
};

export const RECOMMENDATIONS: Record<RiskLevel, string> = {
  low: "Air quality is favourable. No special precautions needed.",
  moderate: "Sensitive groups should limit prolonged outdoor activity and keep windows closed.",
  high: "Limit outdoor activity, wear a mask outside, and keep windows closed.",
  severe: "Stay indoors where possible, wear a mask outside, and keep children and the elderly sheltered.",
};

// Alert levels (progressive tracking / SMS) share the same 4-color scale as
// risk levels, mapped clear->low, watch->moderate, warning->high, alert->severe.
export const ALERT_BADGE_CLASS: Record<AlertLevel, string> = {
  clear: "bg-risk-low/10 text-risk-low border-risk-low/30",
  watch: "bg-risk-moderate/10 text-risk-moderate border-risk-moderate/30",
  warning: "bg-risk-high/10 text-risk-high border-risk-high/30",
  alert: "bg-risk-severe/10 text-risk-severe border-risk-severe/30",
};
