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

/** Poll the runs list slowly, and only while one of its runs is still going. */
export function runsListRefetchInterval(state: PollQueryState): number | false {
  if (state.status === "error") return false;
  const data = state.data;
  if (typeof data !== "object" || data === null || !("items" in data)) {
    return false;
  }
  const items = data.items;
  return Array.isArray(items) && items.some(isActive)
    ? RUNS_LIST_POLL_MS
    : false;
}
