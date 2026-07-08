function ordinal(day: number): string {
  if (day % 10 === 1 && day !== 11) return "st";
  if (day % 10 === 2 && day !== 12) return "nd";
  if (day % 10 === 3 && day !== 13) return "rd";
  return "th";
}

/** e.g. "July 6th 3:28pm" -- plain-language log timestamp, no technical date formats. */
export function formatLogTimestamp(iso: string): string {
  const d = new Date(iso);
  const month = d.toLocaleDateString(undefined, { month: "long" });
  const day = d.getDate();
  let hours = d.getHours();
  const minutes = d.getMinutes().toString().padStart(2, "0");
  const ampm = hours >= 12 ? "pm" : "am";
  hours = hours % 12 || 12;
  return `${month} ${day}${ordinal(day)} ${hours}:${minutes}${ampm}`;
}
