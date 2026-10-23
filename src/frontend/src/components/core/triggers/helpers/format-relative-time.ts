const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 60 * 60 * 1000],
  ["month", 30 * 24 * 60 * 60 * 1000],
  ["week", 7 * 24 * 60 * 60 * 1000],
  ["day", 24 * 60 * 60 * 1000],
  ["hour", 60 * 60 * 1000],
  ["minute", 60 * 1000],
  ["second", 1000],
];

/**
 * "2 minutes ago" / "in 3 hours" in the active UI language. Locale-aware by
 * construction, so no catalog string is needed per unit.
 */
export const formatRelativeTime = (
  time: number,
  locale: string,
  now: number = Date.now(),
): string => {
  const diff = time - now;
  const formatter = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  for (const [unit, size] of UNITS) {
    if (Math.abs(diff) >= size || unit === "second") {
      return formatter.format(Math.round(diff / size), unit);
    }
  }
  return formatter.format(0, "second");
};

export const formatDateTime = (time: number, locale: string): string =>
  new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(time);
