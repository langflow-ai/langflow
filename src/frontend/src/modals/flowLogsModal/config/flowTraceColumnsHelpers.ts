export const formatObjectValue = (value: unknown): string => {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
};

export const coerceNumber = (value: unknown): number | null => {
  if (value === null || value === undefined) return null;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

export const pickFirstNumber = (...candidates: unknown[]): number | null => {
  for (const candidate of candidates) {
    const num = coerceNumber(candidate);
    if (num !== null) return num;
  }
  return null;
};

export const formatLatency = (latencyMs: number | null): string => {
  if (latencyMs === null) return "";
  if (!Number.isFinite(latencyMs)) return "";
  if (latencyMs < 1000) return `${Math.round(latencyMs)} ms`;
  return `${(latencyMs / 1000).toFixed(2)} s`;
};

export const isNegativeStatus = (status: string): boolean => {
  const normalized = status.toLowerCase();
  return (
    normalized === "error" ||
    normalized === "failed" ||
    normalized.includes("fail") ||
    normalized.includes("error") ||
    normalized.includes("exception")
  );
};

export const isPositiveStatus = (status: string): boolean => {
  const normalized = status.toLowerCase();
  return (
    normalized === "success" ||
    normalized === "completed" ||
    normalized === "ok" ||
    normalized.includes("success") ||
    normalized.includes("completed")
  );
};

export const formatRunValue = (
  flowName: string | null | undefined,
  flowId: string | null | undefined,
): string => {
  const name = flowName ?? "";
  const id = flowId ?? "";
  if (!name && !id) return "";
  if (!name) return id;
  if (!id) return name;
  return `${name} - ${id}`;
};
