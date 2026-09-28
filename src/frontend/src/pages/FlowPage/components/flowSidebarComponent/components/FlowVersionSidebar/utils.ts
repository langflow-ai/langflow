import { uiLocale } from "@/utils/format-date";

export function formatTimestamp(dateStr: string): string {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return "Unknown date";
  return date.toLocaleDateString(uiLocale(), {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

type TFunction = (key: string, opts?: object) => string;

/** The time of day, for entries already grouped under their day. */
export function formatTime(dateStr: string): string {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return "";
  return date.toLocaleTimeString(uiLocale(), {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function startOfDay(date: Date): number {
  return new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
  ).getTime();
}

/** The heading a timeline entry is grouped under: Today, Yesterday, or its date. */
export function dayLabel(
  dateStr: string | null,
  t: TFunction,
  now: Date = new Date(),
): string {
  const date = dateStr ? new Date(dateStr) : null;
  if (!date || isNaN(date.getTime())) return t("flowHistory.unknownDate");
  const days = Math.round((startOfDay(now) - startOfDay(date)) / 86_400_000);
  if (days === 0) return t("flowHistory.today");
  if (days === 1) return t("flowHistory.yesterday");
  return date.toLocaleDateString(uiLocale(), {
    month: "short",
    day: "numeric",
    ...(date.getFullYear() !== now.getFullYear() && { year: "numeric" }),
  });
}
