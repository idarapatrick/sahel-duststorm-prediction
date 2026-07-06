import type { RiskLevel } from "./types";

/**
 * The backend doesn't expose visibility/wind-speed/air-index/hourly-breakdown
 * fields yet (LocationPrediction only has probability/risk/dust_event). These
 * are illustrative values derived from the real probability so the richer
 * "Today" UI has something coherent to show, not raw sensor readings. Replace
 * with real fields once the backend adds them.
 */

export interface DerivedStats {
  visibilityKm: number;
  windKmh: number;
  airIndex: number;
}

export function deriveStats(probability: number): DerivedStats {
  return {
    visibilityKm: Math.round((10 - probability * 7) * 10) / 10,
    windKmh: Math.round(12 + probability * 25),
    airIndex: Math.round(30 + probability * 220),
  };
}

export interface HourBucket {
  label: string;
  probability: number;
  risk: RiskLevel;
}

const HOUR_LABELS = ["6a", "9a", "12p", "3p", "6p", "9p"];

function riskForProbability(p: number): RiskLevel {
  if (p > 0.7) return "severe";
  if (p > 0.4) return "high";
  if (p > 0.2) return "moderate";
  return "low";
}

/** Smooth illustrative curve peaking mid-afternoon around the day's overall probability. */
export function deriveHourlyBreakdown(probability: number): HourBucket[] {
  return HOUR_LABELS.map((label, i) => {
    const t = i / (HOUR_LABELS.length - 1);
    const peakShape = Math.sin(t * Math.PI);
    const p = Math.max(0.02, Math.min(0.95, probability * (0.4 + 0.8 * peakShape)));
    return { label, probability: p, risk: riskForProbability(p) };
  });
}

const COMPASS_DIRECTIONS = [
  "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
];

/** Bearing the wind is blowing toward, from its u/v components. */
export function compassDirection(u: number, v: number): string {
  const angle = (Math.atan2(u, v) * 180) / Math.PI;
  const normalized = (angle + 360) % 360;
  return COMPASS_DIRECTIONS[Math.round(normalized / 22.5) % 16];
}

export interface ActionItem {
  icon: "home" | "droplet" | "shield" | "car";
  tint: RiskLevel;
  text: string;
}

/** Always 4 rows (home / droplet / shield / car), matching the reference layout; wording scales with severity. */
export function actionItems(risk: RiskLevel): ActionItem[] {
  if (risk === "low") {
    return [
      { icon: "home", tint: "low", text: "No need to keep windows closed today" },
      { icon: "droplet", tint: "low", text: "Water and food are fine left uncovered" },
      { icon: "shield", tint: "low", text: "No mask needed — enjoy the day" },
      { icon: "car", tint: "low", text: "Normal driving conditions" },
    ];
  }
  if (risk === "moderate") {
    return [
      { icon: "home", tint: "moderate", text: "Keep windows closed around midday" },
      { icon: "droplet", tint: "moderate", text: "Cover drinking water and food" },
      { icon: "shield", tint: "high", text: "Wear a mask if you're out for a while" },
      { icon: "car", tint: "moderate", text: "Drive with headlights on if it gets hazy" },
    ];
  }
  if (risk === "high") {
    return [
      { icon: "home", tint: "high", text: "Keep windows and doors closed" },
      { icon: "droplet", tint: "moderate", text: "Cover drinking water and food" },
      { icon: "shield", tint: "high", text: "Wear a mask outside for any length of time" },
      { icon: "car", tint: "high", text: "Drive slowly — dust lowers visibility" },
    ];
  }
  return [
    { icon: "home", tint: "severe", text: "Stay indoors where possible" },
    { icon: "droplet", tint: "moderate", text: "Cover drinking water and food" },
    { icon: "shield", tint: "severe", text: "Keep children and elderly indoors" },
    { icon: "car", tint: "severe", text: "Avoid driving unless necessary" },
  ];
}

const BEST_TIME_PHRASE: Record<string, string> = {
  "6a": "early morning, before 9am",
  "9a": "mid-morning, around 9–11am",
  "12p": "midday",
  "3p": "mid-afternoon",
  "6p": "early evening",
  "9p": "night",
};

/** Picks the hour bucket with the lowest dust chance and phrases it as a friendly window. */
export function bestTimeOutside(hourly: HourBucket[]): { phrase: string; risk: RiskLevel } {
  const best = hourly.reduce((min, h) => (h.probability < min.probability ? h : min), hourly[0]);
  return { phrase: BEST_TIME_PHRASE[best.label] ?? "early morning", risk: best.risk };
}

export interface AirQualityInfo {
  label: string;
  description: string;
  /** 0-1 position of the marker along the scale bar. */
  position: number;
}

/** Maps the illustrative air index (roughly 30-250) onto a plain-language band, no AQI jargon. */
export function airQualityInfo(airIndex: number): AirQualityInfo {
  const position = Math.max(0, Math.min(1, (airIndex - 30) / 220));
  if (airIndex < 80) {
    return { label: "Good", description: "Air is clear. Fine for spending time outside.", position };
  }
  if (airIndex < 140) {
    return {
      label: "Fair",
      description: "A little dust in the air. Most people are fine outside.",
      position,
    };
  }
  if (airIndex < 200) {
    return {
      label: "Poor",
      description: "Dusty air. People with breathing trouble should limit time outside.",
      position,
    };
  }
  return {
    label: "Very poor",
    description: "Heavy dust in the air. Everyone should limit time outside.",
    position,
  };
}

export type TomorrowTrend = "worse" | "better" | "similar";

export function tomorrowComparison(
  todayProbability: number,
  tomorrowProbability: number
): TomorrowTrend {
  const delta = tomorrowProbability - todayProbability;
  if (delta > 0.1) return "worse";
  if (delta < -0.1) return "better";
  return "similar";
}

const DID_YOU_KNOW_TIPS = [
  "Dust storms in the Sahel can travel thousands of kilometres, sometimes reaching as far as the Americas.",
  "Dust storms often form when strong winds hit dry, loose soil after a long dry spell.",
  "Covering your nose and mouth with a damp cloth can help filter out fine dust particles.",
  "Dust in the air can lower rainfall by blocking sunlight from reaching the ground.",
  "Livestock and crops are also at risk during dust storms — covering water troughs helps keep them safe.",
  "The harmattan wind that carries dust across West Africa usually blows from November to March.",
  "Visibility below 1 km during a dust storm is considered severe enough to disrupt flights and driving.",
];

/** Rotates by day-of-year so the tip changes daily but stays stable within a day. */
export function dailyTip(date: Date = new Date()): string {
  const start = new Date(date.getFullYear(), 0, 0);
  const dayOfYear = Math.floor((date.getTime() - start.getTime()) / 86_400_000);
  return DID_YOU_KNOW_TIPS[dayOfYear % DID_YOU_KNOW_TIPS.length];
}
