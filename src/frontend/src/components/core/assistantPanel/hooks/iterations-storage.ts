/**
 * localStorage primitives for the Assistant's `/iterations N` command — the
 * assistant Agent's step budget (`max_iterations`), which also derives
 * LangGraph's `recursion_limit` (`max_iterations * 2 + 5`). Raising it lets
 * compound build+run+report turns finish instead of hitting the recursion limit.
 *
 * `null` means "unset" — the backend uses the flow default (30). The preference
 * persists across sessions like `/skip-all` and `/history`.
 *
 * Defensive: localStorage can throw in private browsing; a corrupted value
 * degrades to `null` (default) rather than a bogus budget.
 */

const STORAGE_KEY = "langflow-assistant-iterations-limit";
export const MAX_ITERATIONS_LIMIT = 200;
export const DEFAULT_ITERATIONS_LIMIT = 30;

export function readIterationsLimit(): number | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === null) return null;
    const n = Number.parseInt(raw, 10);
    if (Number.isNaN(n) || n < 1 || n > MAX_ITERATIONS_LIMIT) return null;
    return n;
  } catch {
    return null;
  }
}

export interface IterationsCommandResult {
  limit: number | null;
  announcement: string;
  /** False when the input was `/iterations` (report only) or invalid. */
  changed: boolean;
}

/**
 * Parse an `/iterations` command. Returns null when `input` is not an
 * `/iterations` command (so the caller sends it as a normal prompt). Pure — the
 * caller persists `limit` and renders `announcement`.
 */
export function parseIterationsCommand(
  input: string,
  current: number | null,
): IterationsCommandResult | null {
  const trimmed = input.trim();
  if (trimmed !== "/iterations" && !trimmed.startsWith("/iterations ")) {
    return null;
  }
  const arg = trimmed.slice("/iterations".length).trim().toLowerCase();
  if (arg === "") {
    return {
      limit: current,
      changed: false,
      announcement:
        current === null
          ? `Iteration budget: default (${DEFAULT_ITERATIONS_LIMIT}). Use "/iterations N" (1–${MAX_ITERATIONS_LIMIT}) to raise it, "/iterations off" to reset.`
          : `Iteration budget: ${current} steps. "/iterations N" to change, "/iterations off" to reset.`,
    };
  }
  if (arg === "off" || arg === "default" || arg === "reset") {
    return {
      limit: null,
      changed: true,
      announcement: `Iteration budget reset to the default (${DEFAULT_ITERATIONS_LIMIT}).`,
    };
  }
  const n = Number.parseInt(arg, 10);
  if (Number.isNaN(n) || n < 1 || n > MAX_ITERATIONS_LIMIT) {
    return {
      limit: current,
      changed: false,
      announcement: `Invalid iteration budget. Use a number 1–${MAX_ITERATIONS_LIMIT}, or "/iterations off".`,
    };
  }
  return {
    limit: n,
    changed: true,
    announcement: `Iteration budget set to ${n} steps for this session.`,
  };
}

export function writeIterationsLimit(value: number | null): void {
  try {
    if (value === null) {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, String(value));
    }
  } catch {
    // localStorage unavailable (private browsing) — the budget just won't
    // survive a reload; the user can re-issue /iterations.
  }
}
