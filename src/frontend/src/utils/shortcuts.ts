/** Keys that only modify another key and cannot stand alone as a shortcut. */
const MODIFIER_KEYS = new Set([
  "cmd",
  "ctrl",
  "control",
  "alt",
  "option",
  "shift",
  "meta",
  "mod",
]);

/**
 * True when the recorded combination has no non-modifier key (e.g. "Cmd" or
 * "Ctrl + Shift"). Such a combination can never fire, so it must be rejected.
 */
export function isModifierOnlyCombination(recorded: string): boolean {
  const parts = recorded
    .split("+")
    .map((part) => part.trim().toLowerCase())
    .filter(Boolean);
  return parts.length === 0 || parts.every((part) => MODIFIER_KEYS.has(part));
}
