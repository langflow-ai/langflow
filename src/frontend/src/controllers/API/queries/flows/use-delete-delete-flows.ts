import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IDeleteFlows {
  flow_ids: string[];
  expected_edit_revision: Record<string, number>;
}

interface DeleteFlowsResponse {
  deleted: number;
}

export const useDeleteDeleteFlows: useMutationFunctionType<
  undefined,
  IDeleteFlows,
  DeleteFlowsResponse,
  unknown
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteFlowsFn = async (
    payload: IDeleteFlows,
  ): Promise<DeleteFlowsResponse> => {
    const response = await api.delete<DeleteFlowsResponse>(
      `${getURL("FLOWS")}/`,
      {
        data: payload,
      },
    );

    return response.data;
  };

  const mutation: UseMutationResult<
    DeleteFlowsResponse,
    unknown,
    IDeleteFlows
  > = mutate(["useLoginUser"], deleteFlowsFn, {
    ...options,
    onSettled: () => {
      queryClient.refetchQueries({ queryKey: ["useGetFolder"] });
    },
  });

  return mutation;
};
