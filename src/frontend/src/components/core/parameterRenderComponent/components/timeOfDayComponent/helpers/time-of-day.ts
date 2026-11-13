const TIME_24H = /^([01]?\d|2[0-3]):([0-5]\d)$/;
const TIME_12H = /^(0?[1-9]|1[0-2])(?::([0-5]\d))?\s*([ap])\.?\s*m\.?$/i;
const NOON = 12;

const pad = (n: number): string => String(n).padStart(2, "0");

/** Fold the spaces Intl uses (U+202F, U+00A0) so typed text compares equal. */
const normalize = (text: string): string =>
  text
    .replace(/[\s  ]+/g, " ")
    .trim()
    .toLowerCase();

const formatters = new Map<string, Intl.DateTimeFormat>();
const formatter = (locale: string): Intl.DateTimeFormat => {
  let found = formatters.get(locale);
  if (!found) {
    found = new Intl.DateTimeFormat(locale, {
      hour: "numeric",
      minute: "2-digit",
      timeZone: "UTC",
    });
    formatters.set(locale, found);
  }
  return found;
};

/** A saved `HH:MM` time in the reader's clock: "6:30 PM" in English, "18:30" in Portuguese. */
export function formatTimeOfDay(value: string, locale: string): string {
  const match = TIME_24H.exec(value);
  if (!match) return value;
  return formatter(locale).format(
    new Date(Date.UTC(2000, 0, 1, Number(match[1]), Number(match[2]))),
  );
}

const ALL_TIMES = Array.from({ length: 24 * 60 }, (_, minutes) => {
  return `${pad(Math.floor(minutes / 60))}:${pad(minutes % 60)}`;
});
const byLocale = new Map<string, Map<string, string>>();
const localeLookup = (locale: string): Map<string, string> => {
  let lookup = byLocale.get(locale);
  if (!lookup) {
    lookup = new Map(
      ALL_TIMES.map((time) => [normalize(formatTimeOfDay(time, locale)), time]),
    );
    byLocale.set(locale, lookup);
  }
  return lookup;
};

/**
 * The `HH:MM` time a person typed, or null. Accepts 24-hour time, AM/PM, and
 * whatever the reader's locale shows (so "오후 6:30" typed back still parses).
 */
export function parseTimeOfDay(text: string, locale: string): string | null {
  const trimmed = text.trim();
  const match24 = TIME_24H.exec(trimmed);
  if (match24) return `${pad(Number(match24[1]))}:${match24[2]}`;
  const match12 = TIME_12H.exec(trimmed);
  if (match12) {
    const isPm = match12[3].toLowerCase() === "p";
    const hour = (Number(match12[1]) % NOON) + (isPm ? NOON : 0);
    return `${pad(hour)}:${match12[2] ?? "00"}`;
  }
  return localeLookup(locale).get(normalize(trimmed)) ?? null;
}

/** Half-hour suggestions, shown in the reader's clock. */
export const suggestedTimes = (locale: string): string[] =>
  ALL_TIMES.filter((time) => time.endsWith(":00") || time.endsWith(":30")).map(
    (time) => formatTimeOfDay(time, locale),
  );
