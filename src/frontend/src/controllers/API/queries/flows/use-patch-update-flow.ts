import type { UseMutationResult } from "@tanstack/react-query";
import type { ReactFlowJsonObject } from "@xyflow/react";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPatchUpdateFlow {
  id: string;
  name?: string;
  data?: ReactFlowJsonObject;
  description?: string;
  folder_id?: string | null | undefined;
  endpoint_name?: string | null | undefined;
  locked?: boolean | null | undefined;
  access_type?: "PUBLIC" | "PRIVATE" | "PROTECTED";
  flow_type?: "agent" | "workflow";
  a2a_enabled?: boolean;
  a2a_card_overrides?: Record<string, unknown> | null;
}

const isFlowScopedProviderQuery = (
  queryKey: readonly unknown[],
  flowId: string,
): boolean => {
  switch (queryKey[0]) {
    case "useGetTypes":
    case "useGetEnabledModels":
    case "useGetProviderVariables":
    case "useGetGlobalVariables":
      return queryKey[1] === flowId;
    case "useGetModelProviders":
      return queryKey[3] === flowId;
    default:
      return false;
  }
};

export const usePatchUpdateFlow: useMutationFunctionType<
  undefined,
  IPatchUpdateFlow
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const PatchUpdateFlowFn = async ({
    id,
    ...payload
    // biome-ignore lint/suspicious/noExplicitAny: legacy
  }: IPatchUpdateFlow): Promise<any> => {
    const response = await api.patch(`${getURL("FLOWS")}/${id}`, payload);

    return response.data;
  };

  // biome-ignore lint/suspicious/noExplicitAny: legacy
  const mutation: UseMutationResult<IPatchUpdateFlow, any, IPatchUpdateFlow> =
    mutate(["usePatchUpdateFlow"], PatchUpdateFlowFn, {
      ...options,
      onSuccess: (...args) => {
        const [, variables] = args;
        if (Object.hasOwn(variables, "folder_id")) {
          queryClient.invalidateQueries({
            predicate: ({ queryKey }) =>
              isFlowScopedProviderQuery(queryKey, variables.id),
          });
        }
        options?.onSuccess?.(...args);
      },
      onSettled: (...args) => {
        queryClient.invalidateQueries({
          queryKey: ["useGetRefreshFlowsQuery"],
        });
        queryClient.invalidateQueries({
          queryKey: ["useGetFolders"],
        });
        queryClient.invalidateQueries({
          queryKey: ["useGetFolder"],
        });
        options?.onSettled?.(...args);
      },
    });

  return mutation;
};
