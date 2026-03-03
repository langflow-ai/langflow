const pad2 = (num: number): string => String(num).padStart(2, "0");

const hasExplicitTimezone = (value: string): boolean =>
  /([zZ]|[+-]\d{2}:?\d{2})$/.test(value);

export const parseApiTimestamp = (value: unknown): Date | null => {
  if (value === null || value === undefined) return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  const raw = String(value).trim();
  if (!raw) return null;

  const normalized = hasExplicitTimezone(raw)
    ? raw
    : raw.includes("T")
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
