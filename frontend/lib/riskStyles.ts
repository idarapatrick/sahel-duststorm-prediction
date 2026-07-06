import type { AlertLevel, RiskLevel } from "./types";

// Matches the mockup: the risk word stands alone ("Moderate"), no "Risk" suffix.
export const RISK_LABEL: Record<RiskLevel, string> = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  severe: "Severe",
};

export const RISK_SUMMARY: Record<RiskLevel, string> = {
  low: "Air looks clear today. Great day to be outside.",
  moderate: "Some dust likely by afternoon. Fine for most — take it easy if you have breathing trouble.",
  high: "Dust likely for a good part of the day. Limit time outside if you can.",
  severe: "Dust storm conditions expected. Stay indoors where possible.",
};

// Terse severity word -- used for badges and the alert-threshold picker.
// Copy rule: never say "clear"/"warning"/"alert" (backend jargon) to users.
export const ALERT_TERSE_LABEL: Record<AlertLevel, string> = {
  clear: "Calm",
  watch: "Watch",
  warning: "High",
  alert: "Severe",
};

// Narrative status word -- used for the Tracking hero and history rows.
export const ALERT_STATUS_LABEL: Record<AlertLevel, string> = {
  clear: "Calm",
  watch: "Watch",
  warning: "Dust likely",
  alert: "Dust storm",
};
