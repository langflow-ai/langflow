import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { EvaluationInfo } from "./use-get-evaluations";

interface CreateEvaluationParams {
  name?: string;
  dataset_id: string;
  flow_id: string;
  scoring_methods: string[];
  llm_judge_prompt?: string;
  llm_judge_model?: Record<string, any>;
  pass_metric?: string | null;
  pass_threshold?: number;
  run_immediately?: boolean;
}

export const useCreateEvaluation: useMutationFunctionType<
  undefined,
  CreateEvaluationParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createEvaluationFn = async (
    params: CreateEvaluationParams,
  ): Promise<EvaluationInfo> => {
    const response = await api.post<EvaluationInfo>(
      `${getURL("EVALUATIONS")}/?run_immediately=${params.run_immediately ?? false}`,
      {
        name: params.name,
        dataset_id: params.dataset_id,
        flow_id: params.flow_id,
        scoring_methods: params.scoring_methods,
        llm_judge_prompt: params.llm_judge_prompt,
        llm_judge_model: params.llm_judge_model,
        pass_metric: params.pass_metric,
        pass_threshold: params.pass_threshold,
      },
    );
    queryClient.invalidateQueries({ queryKey: ["useGetEvaluations"] });
    return response.data;
  };

  const mutation: UseMutationResult<
    EvaluationInfo,
    any,
    CreateEvaluationParams
  > = mutate(["useCreateEvaluation"], createEvaluationFn, options);

  return mutation;
};
