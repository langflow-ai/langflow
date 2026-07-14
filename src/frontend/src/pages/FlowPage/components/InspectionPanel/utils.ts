import type { InputFieldType } from "@/types/api";

const MAX_DEFAULT_LENGTH = 40;

/**
 * Humanizes a template field default value for the parameter manager rows.
 * Booleans map to Enabled/Disabled, empty values to Empty/None, and long
 * strings are truncated. The returned token for empty/boolean cases is an
 * i18n key suffix resolved by the caller.
 */
export function getDefaultDisplay(
  field: InputFieldType | undefined,
  factoryValue?: unknown,
): { token: "enabled" | "disabled" | "empty" | "none" } | { text: string } {
  const value = factoryValue !== undefined ? factoryValue : field?.value;

  if (field?.type === "bool") {
    return { token: value ? "enabled" : "disabled" };
  }
  if (value === undefined || value === null || value === "") {
    return { token: "empty" };
  }
  if (Array.isArray(value)) {
    return value.length === 0
      ? { token: "none" }
      : { text: truncate(value.join(", ")) };
  }
  if (typeof value === "object") {
    const keys = Object.keys(value as Record<string, unknown>);
    return keys.length === 0
      ? { token: "none" }
      : { text: truncate(JSON.stringify(value)) };
  }
  return { text: truncate(String(value)) };
}

function truncate(text: string): string {
  return text.length > MAX_DEFAULT_LENGTH
    ? `${text.slice(0, MAX_DEFAULT_LENGTH)}…`
    : text;
}
