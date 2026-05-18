export function normalizeWxoName(value: string): string {
  return value.replace(/[\s-]/g, "_").replace(/[^a-zA-Z0-9_]/g, "");
}

export function isValidWxoName(value: string): boolean {
  const normalized = normalizeWxoName(value);
  return normalized.length > 0 && /^[A-Za-z]/.test(normalized);
}

export const INVALID_WXO_TOOL_NAME_MESSAGE =
  "Tool name must start with a letter and contain at least one alphanumeric character.";
