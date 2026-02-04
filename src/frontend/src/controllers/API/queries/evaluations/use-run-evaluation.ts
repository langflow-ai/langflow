import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { EvaluationInfo } from "./use-get-evaluations";

interface RunEvaluationParams {
  evaluationId: string;
}

export const useRunEvaluation: useMutationFunctionType<
  undefined,
  RunEvaluationParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const runEvaluationFn = async (
    params: RunEvaluationParams,
  ): Promise<EvaluationInfo> => {
    const response = await api.post<EvaluationInfo>(
      `${getURL("EVALUATIONS")}/${params.evaluationId}/run`,
    );
    queryClient.invalidateQueries({ queryKey: ["useGetEvaluations"] });
    queryClient.invalidateQueries({
      queryKey: ["useGetEvaluation", params.evaluationId],
    });
    return response.data;
  };

  const mutation: UseMutationResult<EvaluationInfo, any, RunEvaluationParams> =
    mutate(["useRunEvaluation"], runEvaluationFn, options);

  return mutation;
};
