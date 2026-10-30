const UNKNOWN = "—";

export function formatTokenCount(value: number | null | undefined): string {
  return value === null || value === undefined
    ? UNKNOWN
    : new Intl.NumberFormat().format(value);
}

const SMALLEST_SHOWN_USD = 0.0001;

/** `precise` keeps four decimals under a dollar, so amounts cents apart still differ on screen. */
export function formatUsd(
  value: number | null | undefined,
  { precise = false }: { precise?: boolean } = {},
): string {
  if (value === null || value === undefined) return UNKNOWN;
  if (value > 0 && value < SMALLEST_SHOWN_USD) {
    return `< ${formatUsd(SMALLEST_SHOWN_USD)}`;
  }
  const smallAmount = precise ? 1 : 0.01;
  const digits = value !== 0 && value < smallAmount ? 4 : 2;
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatPercent(value: number | null | undefined): string {
  return value === null || value === undefined
    ? UNKNOWN
    : new Intl.NumberFormat(undefined, {
        style: "percent",
        maximumFractionDigits: 1,
      }).format(value);
}

export function formatScore(value: number | null | undefined): string {
  return value === null || value === undefined ? UNKNOWN : value.toFixed(2);
}

/** Milliseconds under a second, seconds above; the unit is written by the locale, not hardcoded. */
export function formatDuration(
  ms: number | null | undefined,
  locale?: string,
): string {
  if (ms === null || ms === undefined) return UNKNOWN;
  const seconds = ms >= 1000;
  return new Intl.NumberFormat(locale, {
    style: "unit",
    unit: seconds ? "second" : "millisecond",
    unitDisplay: "short",
    maximumFractionDigits: seconds ? 1 : 0,
    minimumFractionDigits: seconds ? 1 : 0,
  }).format(seconds ? ms / 1000 : ms);
}

export function formatRunDate(iso: string | null | undefined): string {
  if (!iso) return UNKNOWN;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(iso));
}

/** Signed relative change between two totals, e.g. "+38%"; null when either side is missing. */
export function formatDelta(
  current: number | null | undefined,
  previous: number | null | undefined,
): string | null {
  if (!current || !previous) return null;
  const change = (current - previous) / previous;
  const rounded = Math.round(change * 100);
  return `${rounded > 0 ? "+" : ""}${rounded}%`;
}

/** "a – b", or just "a" when both ends render the same. */
export function formatRange(low: string, high: string): string {
  return low === high ? low : `${low} – ${high}`;
}

/** How many times the smallest value this one is, e.g. "1.7×"; null for the smallest itself or unknowns. */
export function formatRatio(
  value: number | null | undefined,
  smallest: number | null | undefined,
): string | null {
  if (value == null || !smallest || value <= smallest) return null;
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value / smallest)}×`;
}
