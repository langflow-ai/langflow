// Pure formatters shared across the triggers page components.
// Kept dependency-free so they remain trivially unit-testable and
// importable from any component without circular concerns.

export function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString();
}

export function relativeTimeFrom(value: string | null): string {
  if (!value) return "—";
  const target = new Date(value).getTime();
  if (Number.isNaN(target)) return "—";
  const diffMs = target - Date.now();
  const absSec = Math.round(Math.abs(diffMs) / 1000);

  if (absSec < 60) return diffMs >= 0 ? `in ${absSec}s` : `${absSec}s ago`;
  const min = Math.round(absSec / 60);
  if (min < 60) return diffMs >= 0 ? `in ${min}m` : `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return diffMs >= 0 ? `in ${hr}h` : `${hr}h ago`;
  const day = Math.round(hr / 24);
  return diffMs >= 0 ? `in ${day}d` : `${day}d ago`;
}
