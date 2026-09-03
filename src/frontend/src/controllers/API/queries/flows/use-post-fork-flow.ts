import type { UseMutationResult } from "@tanstack/react-query";
import type { ReactFlowJsonObject } from "@xyflow/react";
import type { AxiosError } from "axios";
import { refetchQueriesFresh } from "@/controllers/API/helpers/query-cache";
import type { useMutationFunctionType } from "@/types/api";
import type { FlowType } from "@/types/flow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostForkFlow {
  id: string;
  name?: string;
  data?: ReactFlowJsonObject;
}

/**
 * Creates an inert copy of a flow, carrying whatever graph the caller supplies.
 *
 * The endpoint neutralises exposure server-side, so a copy never inherits an
 * endpoint name, MCP exposure, a webhook or a lock no matter what is posted.
 */
export const usePostForkFlow: useMutationFunctionType<
  undefined,
  IPostForkFlow,
  FlowType,
  AxiosError
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const postForkFlowFn = async ({
    id,
    ...payload
  }: IPostForkFlow): Promise<FlowType> => {
    const response = await api.post<FlowType>(
      `${getURL("FLOWS")}/${id}/fork`,
      payload,
    );
    return response.data;
  };

  const mutation: UseMutationResult<FlowType, AxiosError, IPostForkFlow> =
    mutate(["usePostForkFlow"], postForkFlowFn, {
      ...options,
      onSettled: (response) => {
        if (response) {
          void refetchQueriesFresh(queryClient, {
            queryKey: [
              "useGetRefreshFlowsQuery",
              { get_all: true, header_flows: true },
            ],
          });
        }
      },
    });

  return mutation;
};

export default usePostForkFlow;
