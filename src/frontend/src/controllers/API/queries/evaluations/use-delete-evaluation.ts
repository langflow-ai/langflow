import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteEvaluationParams {
  evaluationId: string;
}

export const useDeleteEvaluation: useMutationFunctionType<
  undefined,
  DeleteEvaluationParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteEvaluationFn = async (
    params: DeleteEvaluationParams,
  ): Promise<void> => {
    await api.delete(`${getURL("EVALUATIONS")}/${params.evaluationId}`);
    queryClient.invalidateQueries({ queryKey: ["useGetEvaluations"] });
  };

  const mutation: UseMutationResult<void, any, DeleteEvaluationParams> = mutate(
    ["useDeleteEvaluation"],
    deleteEvaluationFn,
    options,
  );

  return mutation;
};
