import { type RunStatus, TERMINAL_RUN_STATUSES } from "./types";

export const RUN_POLL_MS = 5000;
// The selected run polls fast; the list only catches runs started elsewhere, so it can lag.
export const RUNS_LIST_POLL_MS = 15000;

const RUN_STATUSES: ReadonlySet<string> = new Set<RunStatus>([
  "queued",
  "running",
  "completed",
  "failed",
  "cancelled",
]);

/** The parts of a react-query state the poll decisions read. */
export interface PollQueryState {
  status: "pending" | "error" | "success";
  data: unknown;
}

function isRunStatus(value: unknown): value is RunStatus {
  return typeof value === "string" && RUN_STATUSES.has(value);
}

function readStatus(value: unknown): RunStatus | undefined {
  if (typeof value !== "object" || value === null || !("status" in value)) {
    return undefined;
  }
  return isRunStatus(value.status) ? value.status : undefined;
}

function isActive(value: unknown): boolean {
  const status = readStatus(value);
  return status !== undefined && !TERMINAL_RUN_STATUSES.has(status);
}

/** Poll a run until it ends; never poll a run that cannot be loaded (deleted, no access). */
export function runRefetchInterval(state: PollQueryState): number | false {
  if (state.status === "error") return false;
  const status = readStatus(state.data);
  return status && TERMINAL_RUN_STATUSES.has(status) ? false : RUN_POLL_MS;
}

// The server starts a comparison's next variant right after a run ends; past this, the chain stopped.
export const NEXT_VARIANT_GRACE_MS = 60000;

function inComparison(value: unknown): boolean {
  return (
    typeof value === "object" &&
    value !== null &&
    "config" in value &&
    typeof value.config === "object" &&
    value.config !== null &&
    "comparison" in value.config &&
    Boolean(value.config.comparison)
  );
}

function comparisonContinues(newest: unknown, now: number): boolean {
  if (typeof newest !== "object" || newest === null) return false;
  const run = newest as {
    status?: unknown;
    finished_at?: unknown;
    config?: { comparison?: { index?: unknown; variants?: unknown } };
  };
  const comparison = run.config?.comparison;
  if (
    !comparison ||
    typeof comparison.index !== "number" ||
    !Array.isArray(comparison.variants) ||
    comparison.index >= comparison.variants.length - 1
  ) {
    return false;
  }
  if (run.status !== "completed" && run.status !== "failed") return false;
  const finished =
    typeof run.finished_at === "string" ? Date.parse(run.finished_at) : NaN;
  return Number.isFinite(finished) && now - finished < NEXT_VARIANT_GRACE_MS;
}

/** Poll the runs list slowly, and only while one of its runs is still going or a comparison moves on. */
export function runsListRefetchInterval(
  state: PollQueryState,
  now: number = Date.now(),
): number | false {
  if (state.status === "error") return false;
  const data = state.data;
  if (typeof data !== "object" || data === null || !("items" in data)) {
    return false;
  }
  const items = data.items;
  if (!Array.isArray(items)) return false;
  const active = items.filter(isActive);
  // A comparison's leaderboard reads the list, so it follows its active variant as fast as a run.
  if (active.some(inComparison)) return RUN_POLL_MS;
  if (active.length > 0) return RUNS_LIST_POLL_MS;
  // Newest first: only the latest run can be waiting for its comparison's next variant.
  return comparisonContinues(items[0], now) ? RUN_POLL_MS : false;
}
