import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { FlowType } from "@/types/flow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IActivateVersion {
  flowId: string;
  historyId: string;
}

export const usePostActivateVersion: useMutationFunctionType<
  undefined,
  IActivateVersion
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const activateVersionFn = async (
    payload: IActivateVersion,
  ): Promise<FlowType> => {
    const response = await api.post<FlowType>(
      `${getURL("FLOWS")}/${payload.flowId}/history/${payload.historyId}/activate`,
    );
    return response.data;
  };

  const mutation: UseMutationResult<FlowType, any, IActivateVersion> = mutate(
    ["usePostActivateVersion"],
    activateVersionFn,
    {
      ...options,
      onSettled: (_, __, variables) => {
        queryClient.refetchQueries({
          queryKey: ["useGetFlowHistory", { flowId: variables?.flowId }],
        });
        queryClient.refetchQueries({
          queryKey: [
            "useGetRefreshFlowsQuery",
            { get_all: true, header_flows: true },
          ],
        });
      },
    },
  );

  return mutation;
};
