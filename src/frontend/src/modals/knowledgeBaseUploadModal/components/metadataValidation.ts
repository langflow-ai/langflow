import type { MetadataPair } from "./MetadataEditor";

export const KEY_PATTERN = /^[a-z0-9_]{1,32}$/;
export const MAX_KEYS = 16;
export const MAX_VALUE_LENGTH = 256;

export type PairValidation = { ok: true } | { ok: false; error: string };

/**
 * Validate a single metadata row in isolation. Pure — does not look at
 * other rows or any external state. Duplicate-key checks live in
 * ``validateMetadataPairs`` where the full set is available.
 */
export const validateMetadataPair = (
  key: string,
  value: string,
): PairValidation => {
  const trimmedKey = key.trim();
  const trimmedValue = value.trim();
  // Empty rows are treated as not-yet-filled-in, not invalid. The set
  // validator strips them; the form gate ignores them.
  if (!trimmedKey && !trimmedValue) return { ok: true };
  if (!trimmedKey) {
    return { ok: false, error: "Key is required when a value is set." };
  }
  if (!trimmedValue) {
    return { ok: false, error: "Value is required when a key is set." };
  }
  if (!KEY_PATTERN.test(trimmedKey)) {
    return {
      ok: false,
      error: "Keys must be 1-32 lowercase letters, digits, or underscores.",
    };
  }
  if (trimmedValue.length > MAX_VALUE_LENGTH) {
    return {
      ok: false,
      error: `Values must be ${MAX_VALUE_LENGTH} characters or fewer.`,
    };
  }
  return { ok: true };
};

export interface PairsValidation {
  ok: boolean;
  /** Per-row errors keyed by index. Empty when ``ok`` is true. */
  errors: Record<number, string>;
  /** Set-level error (count limit). Set independently of per-row errors. */
  setError?: string;
}

/**
 * Validate the entire metadata set. Combines per-row checks with
 * cross-row rules (duplicate keys, max count).
 */
export const validateMetadataPairs = (
  pairs: MetadataPair[],
): PairsValidation => {
  const errors: Record<number, string> = {};
  const seenKeys = new Map<string, number>();

  pairs.forEach((pair, index) => {
    const rowResult = validateMetadataPair(pair.key, pair.value);
    if (!rowResult.ok) {
      errors[index] = rowResult.error;
      return;
    }
    const trimmedKey = pair.key.trim();
    if (!trimmedKey) return; // fully-empty row
    if (seenKeys.has(trimmedKey)) {
      errors[index] = "Duplicate key.";
      return;
    }
    seenKeys.set(trimmedKey, index);
  });

  const setError =
    pairs.length > MAX_KEYS
      ? `Up to ${MAX_KEYS} metadata fields per ingestion.`
      : undefined;

  return {
    ok: Object.keys(errors).length === 0 && !setError,
    errors,
    setError,
  };
};

/**
 * Convenience: returns only the pairs that pass every rule, trimmed.
 * Use when the caller wants the "clean" set (e.g. for display in a
 * summary) without re-implementing the rule set.
 */
export const filterValidMetadataPairs = (
  pairs: MetadataPair[],
): MetadataPair[] => {
  const seen = new Set<string>();
  const result: MetadataPair[] = [];
  for (const pair of pairs) {
    const rowResult = validateMetadataPair(pair.key, pair.value);
    if (!rowResult.ok) continue;
    const key = pair.key.trim();
    const value = pair.value.trim();
    if (!key || !value || seen.has(key)) continue;
    seen.add(key);
    result.push({ key, value });
  }
  return result;
};
