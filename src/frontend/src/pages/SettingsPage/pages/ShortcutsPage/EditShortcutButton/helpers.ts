import { toCamelCase, toTitleCase } from "@/utils/utils";

type ShortcutItem = {
  name: string;
  shortcut: string;
  display_name: string;
};

export function findShortcutByName(
  shortcuts: ShortcutItem[],
  shortcutName: string,
): ShortcutItem | undefined {
  return shortcuts.find(
    (shortcut) =>
      toCamelCase(shortcut.name) === toCamelCase(shortcutName ?? ""),
  );
}

export function isDuplicateCombination(
  shortcuts: ShortcutItem[],
  currentName: string,
  newCombination: string,
): boolean {
  return shortcuts.some(
    (existing) =>
      existing.name !== currentName &&
      existing.shortcut.toLowerCase() === newCombination.toLowerCase(),
  );
}

export function getFixedCombination(
  oldKey: string | null,
  key: string,
): string {
  if (oldKey === null) {
    return `${key.length > 0 ? toTitleCase(key) : toTitleCase(key)}`;
  }
  return `${
    oldKey.length > 0 ? toTitleCase(oldKey) : oldKey.toUpperCase()
  } + ${key.length > 0 ? toTitleCase(key) : key.toUpperCase()}`;
}

export function checkForKeys(keys: string, keyToCompare: string): boolean {
  const keysArr = keys.split(" ");
  return keysArr.some(
    (k) => k.toLowerCase().trim() === keyToCompare.toLowerCase().trim(),
  );
}

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

export function normalizeRecordedCombination(recorded: string): string {
  const parts = recorded.split(" ");
  if (
    parts[0]?.toLowerCase().includes("ctrl") ||
    parts[0]?.toLowerCase().includes("cmd")
  ) {
    parts[0] = "mod";
  }
  return parts.join("").toLowerCase();
}
