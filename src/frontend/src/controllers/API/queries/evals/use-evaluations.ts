import { keepPreviousData } from "@tanstack/react-query";
import type {
  useMutationFunctionType,
  useQueryFunctionType,
} from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import {
  type Evaluation,
  type EvaluationResult,
  type EvaluationRun,
  type FlowCheckReport,
  type Page,
  type RunEstimate,
  type ScorerSpec,
  TERMINAL_RUN_STATUSES,
} from "./types";

const EVALUATIONS_KEY = "useGetEvaluations";
const EVALUATION_KEY = "useGetEvaluation";
const RUNS_KEY = "useGetEvaluationRuns";
const RUN_KEY = "useGetEvaluationRun";
const RESULTS_KEY = "useGetEvaluationResults";
export const RUN_POLL_MS = 5000;

export interface EvaluationCreatePayload {
  flow_id: string;
  dataset_id: string;
  name?: string;
  output_vertex_id?: string | null;
  scorers: ScorerSpec[];
  pass_threshold: number;
}

export const useGetEvaluations: useQueryFunctionType<
  { flowId?: string; page?: number; size?: number },
  Page<Evaluation>
> = ({ flowId, page = 1, size = 50 }, options) => {
  const { query } = UseRequestProcessor();
  return query(
    [EVALUATIONS_KEY, { flowId, page, size }],
    async () =>
      (
        await api.get<Page<Evaluation>>(getURL("EVALUATIONS"), {
          params: { flow_id: flowId, page, size },
        })
      ).data,
    options,
  );
};

export const useGetEvaluation: useQueryFunctionType<
  { evaluationId: string },
  Evaluation
> = ({ evaluationId }, options) => {
  const { query } = UseRequestProcessor();
  return query(
    [EVALUATION_KEY, evaluationId],
    async () =>
      (await api.get<Evaluation>(`${getURL("EVALUATIONS")}/${evaluationId}`))
        .data,
    { enabled: Boolean(evaluationId), ...options },
  );
};

export const useGetEvaluationRuns: useQueryFunctionType<
  { evaluationId: string; poll?: boolean },
  Page<EvaluationRun>
> = ({ evaluationId, poll = false }, options) => {
  const { query } = UseRequestProcessor();
  return query(
    [RUNS_KEY, evaluationId],
    async () =>
      (
        await api.get<Page<EvaluationRun>>(
          `${getURL("EVALUATIONS")}/${evaluationId}/runs`,
          { params: { size: 100 } },
        )
      ).data,
    {
      enabled: Boolean(evaluationId),
      refetchInterval: poll ? RUN_POLL_MS : false,
      ...options,
    },
  );
};

export const useGetEvaluationRun: useQueryFunctionType<
  { runId: string },
  EvaluationRun
> = ({ runId }, options) => {
  const { query } = UseRequestProcessor();
  return query(
    [RUN_KEY, runId],
    async () =>
      (await api.get<EvaluationRun>(`${getURL("EVALUATION_RUNS")}/${runId}`))
        .data,
    {
      enabled: Boolean(runId),
      refetchInterval: (state: { state: { data?: EvaluationRun } }) => {
        const status = state.state.data?.status;
        return status && TERMINAL_RUN_STATUSES.has(status)
          ? false
          : RUN_POLL_MS;
      },
      ...options,
    } as Parameters<typeof query>[2],
  );
};

export const useGetEvaluationResults: useQueryFunctionType<
  {
    runId: string;
    page?: number;
    size?: number;
    poll?: boolean;
    /** Changes whenever the run makes progress, so the last rows load even after polling stops. */
    progressKey?: string;
  },
  Page<EvaluationResult>
> = ({ runId, page = 1, size = 50, poll = false, progressKey }, options) => {
  const { query } = UseRequestProcessor();
  return query(
    [RESULTS_KEY, runId, { page, size, progressKey }],
    async () =>
      (
        await api.get<Page<EvaluationResult>>(
          `${getURL("EVALUATION_RUNS")}/${runId}/results`,
          { params: { page, size } },
        )
      ).data,
    {
      enabled: Boolean(runId),
      refetchInterval: poll ? RUN_POLL_MS : false,
      placeholderData: keepPreviousData,
      ...options,
    },
  );
};

export const useCheckFlowForEvaluation: useQueryFunctionType<
  { flowId: string; outputVertexId?: string | null },
  FlowCheckReport
> = ({ flowId, outputVertexId }, options) => {
  const { query } = UseRequestProcessor();
  return query(
    ["useCheckFlowForEvaluation", flowId, outputVertexId ?? null],
    async () =>
      (
        await api.post<FlowCheckReport>(
          `${getURL("EVALUATIONS")}/check`,
          null,
          {
            params: {
              flow_id: flowId,
              output_vertex_id: outputVertexId || undefined,
            },
          },
        )
      ).data,
    // The flow may have changed since the last open: always check the saved draft again.
    {
      enabled: Boolean(flowId),
      staleTime: 0,
      refetchOnMount: "always",
      ...options,
    },
  );
};

export const useEstimateEvaluation: useQueryFunctionType<
  { flowId: string; datasetId: string; scorers: ScorerSpec[] },
  RunEstimate
> = ({ flowId, datasetId, scorers }, options) => {
  const { query } = UseRequestProcessor();
  return query(
    ["useEstimateEvaluation", flowId, datasetId, scorers.map((s) => s.type)],
    async () =>
      (
        await api.post<RunEstimate>(`${getURL("EVALUATIONS")}/estimate`, {
          flow_id: flowId,
          dataset_id: datasetId,
          scorers,
        })
      ).data,
    {
      enabled: Boolean(flowId && datasetId),
      // Keep the last estimate on screen while a scorer change refetches it, so the box does not flash.
      placeholderData: keepPreviousData,
      ...options,
    },
  );
};

function useInvalidateEvaluations() {
  const { queryClient } = UseRequestProcessor();
  return (evaluationId?: string) => {
    queryClient.invalidateQueries({ queryKey: [EVALUATIONS_KEY] });
    if (evaluationId) {
      queryClient.invalidateQueries({
        queryKey: [EVALUATION_KEY, evaluationId],
      });
      queryClient.invalidateQueries({ queryKey: [RUNS_KEY, evaluationId] });
    }
  };
}

export const useCreateEvaluation: useMutationFunctionType<
  undefined,
  { payload: EvaluationCreatePayload; run: boolean },
  Evaluation | EvaluationRun
> = (options) => {
  const { mutate } = UseRequestProcessor();
  const invalidate = useInvalidateEvaluations();
  return mutate(
    ["useCreateEvaluation"],
    async ({ payload, run }) =>
      (
        await api.post<Evaluation | EvaluationRun>(
          getURL("EVALUATIONS"),
          payload,
          { params: { run } },
        )
      ).data,
    { ...options, onSettled: () => invalidate() },
  );
};

export const useDeleteEvaluation: useMutationFunctionType<
  undefined,
  { evaluationId: string }
> = (options) => {
  const { mutate } = UseRequestProcessor();
  const invalidate = useInvalidateEvaluations();
  return mutate(
    ["useDeleteEvaluation"],
    async ({ evaluationId }) =>
      (await api.delete(`${getURL("EVALUATIONS")}/${evaluationId}`)).data,
    { ...options, onSettled: () => invalidate() },
  );
};

export const useStartEvaluationRun: useMutationFunctionType<
  { evaluationId: string },
  { flowVersionId: string | null },
  EvaluationRun
> = ({ evaluationId }, options) => {
  const { mutate } = UseRequestProcessor();
  const invalidate = useInvalidateEvaluations();
  return mutate(
    ["useStartEvaluationRun", evaluationId],
    async ({ flowVersionId }) =>
      (
        await api.post<EvaluationRun>(
          `${getURL("EVALUATIONS")}/${evaluationId}/runs`,
          { flow_version_id: flowVersionId },
        )
      ).data,
    { retry: false, ...options, onSettled: () => invalidate(evaluationId) },
  );
};

export const useCancelEvaluationRun: useMutationFunctionType<
  { runId: string; evaluationId: string },
  undefined,
  EvaluationRun
> = ({ runId, evaluationId }, options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const invalidate = useInvalidateEvaluations();
  return mutate(
    ["useCancelEvaluationRun", runId],
    async () =>
      (
        await api.post<EvaluationRun>(
          `${getURL("EVALUATION_RUNS")}/${runId}/cancel`,
        )
      ).data,
    {
      retry: false,
      ...options,
      onSettled: () => {
        invalidate(evaluationId);
        queryClient.invalidateQueries({ queryKey: [RUN_KEY, runId] });
      },
    },
  );
};

export function exportUrl(kind: "dataset" | "run", id: string): string {
  return kind === "dataset"
    ? `${getURL("DATASETS")}/${id}/export`
    : `${getURL("EVALUATION_RUNS")}/${id}/export`;
}
