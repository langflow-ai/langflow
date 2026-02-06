import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface EvaluationResultInfo {
  id: string;
  evaluation_id: string;
  dataset_item_id?: string;
  input: string;
  expected_output: string;
  actual_output?: string;
  duration_ms?: number;
  scores: Record<string, number>;
  passed: boolean;
  error?: string;
  order: number;
  conversation_id?: string;
  created_at?: string;
  flow_tokens?: number;
  llm_judge_tokens?: number;
}

export interface EvaluationInfo {
  id: string;
  name?: string;
  status: "pending" | "running" | "completed" | "failed";
  scoring_methods: string[];
  user_id: string;
  dataset_id: string;
  flow_id: string;
  dataset_name?: string;
  flow_name?: string;
  created_at?: string;
  updated_at?: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  total_items: number;
  completed_items: number;
  passed_items: number;
  mean_score?: number;
  mean_duration_ms?: number;
  total_runtime_ms?: number;
  total_flow_tokens?: number;
  total_llm_judge_tokens?: number;
  pass_metric?: string | null;
  pass_threshold?: number;
  results?: EvaluationResultInfo[];
}

interface GetEvaluationsParams {
  flowId?: string;
}

export const useGetEvaluations: useQueryFunctionType<
  GetEvaluationsParams,
  EvaluationInfo[]
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getEvaluationsFn = async (): Promise<EvaluationInfo[]> => {
    const url = params?.flowId
      ? `${getURL("EVALUATIONS")}/?flow_id=${params.flowId}`
      : `${getURL("EVALUATIONS")}/`;
    const res = await api.get(url);
    return res.data;
  };

  const queryResult: UseQueryResult<EvaluationInfo[], any> = query(
    ["useGetEvaluations", params?.flowId],
    getEvaluationsFn,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
