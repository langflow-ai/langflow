import type { UseMutationResult } from "@tanstack/react-query";
import type { ReactFlowJsonObject } from "@xyflow/react";
import { useFolderStore } from "@/stores/foldersStore";
import type { useMutationFunctionType } from "@/types/api";
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
  mcp_enabled: boolean | undefined;
}

export const usePostAddFlow: useMutationFunctionType<
  undefined,
  IPostAddFlow
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const postAddFlowFn = async (payload: IPostAddFlow): Promise<any> => {
    const response = await api.post(`${getURL("FLOWS")}/`, {
      name: payload.name,
      data: payload.data,
      description: payload.description,
      is_component: payload.is_component,
      folder_id: payload.folder_id || null,
      icon: payload.icon || null,
      gradient: payload.gradient || null,
      endpoint_name: payload.endpoint_name || null,
      tags: payload.tags || null,
      mcp_enabled: payload.mcp_enabled || null,
    });
    return response.data;
  };

  const mutation: UseMutationResult<IPostAddFlow, any, IPostAddFlow> = mutate(
    ["usePostAddFlow"],
    postAddFlowFn,
    {
      ...options,
      onSettled: (response) => {
        if (response) {
          queryClient.refetchQueries({
            queryKey: [
              "useGetRefreshFlowsQuery",
              { get_all: true, header_flows: true },
            ],
          });

          queryClient.refetchQueries({
            queryKey: ["useGetFolder", response.folder_id ?? myCollectionId],
          });
        }
      },
    },
  );

  return mutation;
};
