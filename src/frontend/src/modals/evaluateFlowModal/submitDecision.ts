import type { RunEstimate } from "@/controllers/API/queries/evals/types";

export type SubmitDecision = "wait" | "confirm" | "run";

export interface EstimateQueryState {
  data: RunEstimate | undefined;
  isFetching: boolean;
  isPlaceholderData: boolean;
  isError: boolean;
}

/**
 * Whether Submit may start the run straight away. A run that may spend money is
 * never started without the confirm step: a failed estimate asks anyway, and a
 * loading or stale (placeholder) estimate holds the button until it settles.
 */
export function submitDecision(estimate: EstimateQueryState): SubmitDecision {
  if (estimate.isError) return "confirm";
  if (estimate.isFetching || estimate.isPlaceholderData || !estimate.data) {
    return "wait";
  }
  return estimate.data.llm_calls > 0 ? "confirm" : "run";
}
