import type { useMutationFunctionType } from "@/types/api";
import type { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IDeleteFlows {
  flow_ids: string[];
}

export const useDeleteDeleteFlows: useMutationFunctionType<
  undefined,
  IDeleteFlows
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteFlowsFn = async (payload: IDeleteFlows): Promise<any> => {
    const response = await api.delete<any>(`${getURL("FLOWS")}/`, {
      data: payload.flow_ids,
    });

    return response.data;
  };

  const mutation: UseMutationResult<IDeleteFlows, any, IDeleteFlows> = mutate(
    ["useLoginUser"],
    deleteFlowsFn,
    {
      ...options,
      onSettled: () => {
        queryClient.refetchQueries({ queryKey: ["useGetFolder"] });
      },
    },
  );

  return mutation;
};
