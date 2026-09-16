import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FlowBinding, FlowOutputChoice } from "@/pages/MainPage/entities";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export type EvalCase = {
  id: string;
  name: string;
  input: string;
  reference: string;
  minimum_score: number;
  require_sourced_artifact: boolean;
  require_supported_claims: boolean;
  expected_policy: "compliant" | "violation" | null;
  max_latency_ms: number | null;
  max_cost_usd: number | null;
};
export type EvalConfig = {
  workflow_id: string | null;
  candidate_digest: string | null;
  scorer: FlowBinding | null;
  cases: EvalCase[];
};
export type EvalContext = {
  config: EvalConfig;
  revision: string;
  targets: { workflow_id: string; candidate_digest: string; name: string }[];
  scorers: FlowOutputChoice[];
};
export type EvalCaseResult = {
  case_id: string;
  passed: boolean;
  failures: string[];
  latency_ms: number | null;
  cost_usd: number | null;
  workflow_job_id: string | null;
  scorer_job_id: string | null;
  verdict: {
    score: number;
    reason: string;
    claim_support: string;
    policy: string;
  } | null;
  output: Record<string, unknown> | null;
};
export type EvalRun = {
  id: string;
  status: string;
  created_at: string;
  passed: boolean;
  candidate_digest: string;
  scorer_digest: string;
  suite_revision: string;
  cancel_requested?: boolean;
  error?: string | null;
  pending_approval?: {
    job_id: string;
    phase: "candidate" | "scorer";
    case_id: string;
    request: Record<string, unknown>;
  } | null;
  result: {
    current?: {
      job_id: string;
      phase: "candidate" | "scorer";
      case_id: string;
    } | null;
    suite: EvalConfig;
    cases: EvalCaseResult[];
    complete: boolean;
  } | null;
};
export const evalURL = (id: string) =>
  `${getURL("PROJECTS")}/${encodeURIComponent(id)}/evaluations`;

export function useEvalSuite(projectId: string) {
  return useQuery({
    queryKey: ["evalSuite", projectId],
    queryFn: async ({ signal }) =>
      (await api.get<EvalContext>(evalURL(projectId), { signal })).data,
    retry: false,
  });
}

export function useEvalRuns(projectId: string, watching: boolean) {
  return useQuery({
    queryKey: ["evalRuns", projectId],
    queryFn: async ({ signal }) =>
      (await api.get<EvalRun[]>(`${evalURL(projectId)}/runs`, { signal })).data,
    retry: false,
    refetchInterval: (query) =>
      watching || query.state.data?.some(isEvalRunActive) ? 2000 : false,
  });
}

export function useRunEvalSuite(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      run_id: string;
      expected_revision: string;
      expected_candidate_digest: string;
    }) => (await api.post<EvalRun>(`${evalURL(projectId)}/runs`, body)).data,
    retry: false,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["evalRuns", projectId] });
    },
  });
}

export function isEvalRunActive(run: EvalRun): boolean {
  return ["queued", "in_progress", "suspended"].includes(run.status);
}

export function useCancelEvalRun(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (runId: string) =>
      (
        await api.post<EvalRun>(
          `${evalURL(projectId)}/runs/${encodeURIComponent(runId)}/cancel`,
        )
      ).data,
    retry: false,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["evalRuns", projectId] });
    },
  });
}

/** Comparison requires the same cases, thresholds, root workflow and frozen scorer. */
export function comparableRuns(left: EvalRun, right: EvalRun): boolean {
  return (
    left.status === "completed" &&
    right.status === "completed" &&
    left.result?.complete === true &&
    right.result?.complete === true &&
    left.suite_revision === right.suite_revision &&
    left.scorer_digest === right.scorer_digest
  );
}
