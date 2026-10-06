import type { UseMutationResult } from "@tanstack/react-query";
import type { ReactFlowJsonObject } from "@xyflow/react";
import type { AxiosError } from "axios";
import { refetchQueriesFresh } from "@/controllers/API/helpers/query-cache";
import { useFolderStore } from "@/stores/foldersStore";
import type { useMutationFunctionType } from "@/types/api";
import type { FlowType } from "@/types/flow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostAddFlow {
  name: string;
  data: ReactFlowJsonObject;
  description: string;
  is_component: boolean;
  folder_id: string;
  endpoint_name: string | undefined;
  icon: string | undefined;
  gradient: string | undefined;
  tags: string[] | undefined;
  locked?: boolean | null;
  mcp_enabled: boolean | undefined;
}

interface PostAddFlowErrorResponse {
  detail?: string | Array<{ type?: string }>;
}

export const usePostAddFlow: useMutationFunctionType<
  undefined,
  IPostAddFlow,
  FlowType,
  AxiosError<PostAddFlowErrorResponse>
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const postAddFlowFn = async (payload: IPostAddFlow): Promise<FlowType> => {
    const response = await api.post<FlowType>(`${getURL("FLOWS")}/`, {
      name: payload.name,
      data: payload.data,
      description: payload.description,
      is_component: payload.is_component,
      folder_id: payload.folder_id || null,
      icon: payload.icon || null,
      gradient: payload.gradient || null,
      endpoint_name: payload.endpoint_name || null,
      tags: payload.tags || null,
      locked: payload.locked ?? null,
      mcp_enabled: payload.mcp_enabled || null,
    });
    return response.data;
  };

  const mutation: UseMutationResult<
    FlowType,
    AxiosError<PostAddFlowErrorResponse>,
    IPostAddFlow
  > = mutate(["usePostAddFlow"], postAddFlowFn, {
    ...options,
    // Fire-and-forget on purpose: TanStack dispatches the mutation's
    // "success" only after this callback settles, so awaiting the refetches
    // would hold up every caller of `addFlow` — including the navigation to
    // the flow that was just created.
    onSettled: (response) => {
      if (response) {
        void refetchQueriesFresh(queryClient, {
          queryKey: [
            "useGetRefreshFlowsQuery",
            { get_all: true, header_flows: true },
          ],
        });

        void refetchQueriesFresh(queryClient, {
          queryKey: ["useGetFolder", response.folder_id ?? myCollectionId],
        });
      }
    },
  });

  return mutation;
};
