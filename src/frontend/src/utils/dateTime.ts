import { normalizeApiTimestamp } from "@/customization/utils/custom-normalizeApiTimeStamp";

const pad2 = (num: number): string => String(num).padStart(2, "0");

const hasExplicitTimezone = (value: string): boolean =>
  /([zZ]|[+-]\d{2}:?\d{2})$/.test(value);

// Backend Message timestamps use "%Y-%m-%d %H:%M:%S.%f %Z" (e.g.
// "2024-01-02 03:04:05.571339 UTC"), which WebKit's Date parser rejects.
const BACKEND_UTC_TIMESTAMP =
  /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}(?:\.\d+)?) UTC$/;

// Anchored so the "T" inside a trailing "UTC" is not read as an ISO marker.
const ISO_DATE_PREFIX = /^\d{4}-\d{2}-\d{2}T/;

const toIsoUtc = (raw: string): string => {
  const backendUtc = BACKEND_UTC_TIMESTAMP.exec(raw);
  return backendUtc ? `${backendUtc[1]}T${backendUtc[2]}Z` : raw;
};

export const parseApiTimestamp = (value: unknown): Date | null => {
  if (value === null || value === undefined) return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  const raw = toIsoUtc(normalizeApiTimestamp(String(value).trim()));
  if (!raw) return null;

  const normalized = hasExplicitTimezone(raw)
    ? raw
    : ISO_DATE_PREFIX.test(raw)
      ? `${raw}Z`
      : raw;

  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
};

export const formatSmartTimestamp = (value: unknown): string => {
  const date = parseApiTimestamp(value);
  if (!date) return value ? String(value) : "";

  const now = new Date();

  const time = new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    hour12: false,
    minute: "2-digit",
    second: "2-digit",
    timeZone: "UTC",
  }).format(date);

  const isToday =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();

  if (isToday) return time;

  const sameYear = date.getFullYear() === now.getFullYear();
  if (sameYear) {
    return new Intl.DateTimeFormat(undefined, {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      hour12: false,
      minute: "2-digit",
      second: "2-digit",
      timeZone: "UTC",
    }).format(date);
  }

  const ddmmyyyy = `${pad2(date.getDate())}/${pad2(date.getMonth() + 1)}/${date.getFullYear()}`;
  return `${ddmmyyyy} ${time}`;
};
