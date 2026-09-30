export const KEY_PATTERN = /^[a-z0-9_]{1,32}$/;

export type ValidationResult =
  | { ok: true; key: string; value: string }
  | { ok: false; error: string };

/**
 * Pure validation for the metadata filter inputs. Mirrors backend rules
 * so an obviously malformed key (e.g. uppercase, punctuation, empty) is
 * rejected before the request is sent.
 */
export const validateMetadataFilter = (
  key: string,
  value: string,
): ValidationResult => {
  const trimmedKey = key.trim();
  const trimmedValue = value.trim();
  if (!trimmedKey || !trimmedValue) {
    return { ok: false, error: "Key and value are required." };
  }
  if (!KEY_PATTERN.test(trimmedKey)) {
    return {
      ok: false,
      error: "Key must be 1-32 lowercase letters, digits, or underscores.",
    };
  }
  return { ok: true, key: trimmedKey, value: trimmedValue };
};
