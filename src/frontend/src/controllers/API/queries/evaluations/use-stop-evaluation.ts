import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { EvaluationInfo } from "./use-get-evaluations";

interface StopEvaluationParams {
  evaluationId: string;
}

export const useStopEvaluation: useMutationFunctionType<
  undefined,
  StopEvaluationParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const stopEvaluationFn = async (
    params: StopEvaluationParams,
  ): Promise<EvaluationInfo> => {
    const response = await api.post<EvaluationInfo>(
      `${getURL("EVALUATIONS")}/${params.evaluationId}/stop`,
    );
    queryClient.invalidateQueries({ queryKey: ["useGetEvaluations"] });
    queryClient.invalidateQueries({
      queryKey: ["useGetEvaluation", params.evaluationId],
    });
    return response.data;
  };

  const mutation: UseMutationResult<EvaluationInfo, any, StopEvaluationParams> =
    mutate(["useStopEvaluation"], stopEvaluationFn, options);

  return mutation;
};
