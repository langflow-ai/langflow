/**
 * localStorage primitives for the Assistant input's recent-commands history.
 *
 * Mirrors the shell/REPL pattern: pressing Up at the start of the input
 * recalls the most recent message; subsequent Ups walk further back.
 * History caps at the last 10 entries to keep the storage payload small
 * and the recall predictable.
 *
 * Both helpers are defensive: localStorage can throw under sandbox or
 * private-browsing restrictions, and a corrupted payload must not crash
 * the assistant panel or surface garbage into the textarea.
 */

const STORAGE_KEY = "langflow-assistant-input-history";
const MAX_HISTORY = 10;

export function readHistory(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === null) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    if (!parsed.every((v): v is string => typeof v === "string")) return [];
    return parsed;
  } catch {
    return [];
  }
}

export function pushHistory(value: string): void {
  const trimmed = value.trim();
  if (trimmed === "") return;
  try {
    const current = readHistory();
    if (current[0] === value) return; // dedup against latest
    const next = [value, ...current].slice(0, MAX_HISTORY);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // localStorage unavailable — feature degrades silently. The next
    // session simply starts without history.
  }
}
