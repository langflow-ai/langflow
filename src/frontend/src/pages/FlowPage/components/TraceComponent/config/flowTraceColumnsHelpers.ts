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
