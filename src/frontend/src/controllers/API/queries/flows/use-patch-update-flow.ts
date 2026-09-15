import type {
  Query,
  QueryClient,
  UseMutationResult,
} from "@tanstack/react-query";
import type { ReactFlowJsonObject } from "@xyflow/react";
import type { useMutationFunctionType } from "@/types/api";
import type { FlowType } from "@/types/flow";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface IPatchUpdateFlow {
  id: string;
  /** Revision observed in the latest authoritative flow response. */
  edit_revision: number;
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
  /** Internal signal; stripped before PATCHing the API. */
  providerScopeChanged?: boolean;
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

export const clearFlowScopedProviderQueries = async (
  queryClient: QueryClient,
  flowId: string,
): Promise<void> => {
  const predicate = ({ queryKey }: Query) =>
    isFlowScopedProviderQuery(queryKey, flowId);

  // A project move changes the trusted scope behind these flow-id-only keys.
  // Cancel first so an in-flight response from the previous project cannot
  // repopulate the cache. Reset (rather than only invalidate/remove) also
  // clears data held by active observers before their project-B refetch.
  await queryClient.cancelQueries({ predicate });
  await queryClient.resetQueries({ predicate });
};

export const usePatchUpdateFlow: useMutationFunctionType<
  undefined,
  IPatchUpdateFlow
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const PatchUpdateFlowFn = async ({
    id,
    edit_revision,
    providerScopeChanged: _providerScopeChanged,
    ...payload
  }: IPatchUpdateFlow): Promise<FlowType> => {
    const response = await api.patch<FlowType>(
      `${getURL("FLOWS")}/${id}`,
      payload,
      {
        headers: { "If-Match": `"flow:${id}:${edit_revision}"` },
      },
    );

    return response.data;
  };

  const mutation: UseMutationResult<FlowType, unknown, IPatchUpdateFlow> =
    mutate(["usePatchUpdateFlow"], PatchUpdateFlowFn, {
      ...options,
      onSuccess: async (...args) => {
        const [, variables] = args;
        if (variables.providerScopeChanged) {
          await clearFlowScopedProviderQueries(queryClient, variables.id);
        }
        await options?.onSuccess?.(...args);
      },
      onSettled: async (...args) => {
        const [, error, variables] = args;
        const status = (error as { response?: { status?: number } } | null)
          ?.response?.status;
        if (status === 403 || status === 404) {
          // Drop the old allow projection immediately, then ask the existing
          // permission endpoint again without replacing the unsaved graph.
          await queryClient.resetQueries({
            queryKey: ["useGetEffectivePermissions"],
            predicate: ({ queryKey }) =>
              queryKey[2] === "flow" &&
              Array.isArray(queryKey[3]) &&
              queryKey[3].includes(variables.id),
          });
        }
        queryClient.invalidateQueries({
          queryKey: ["useGetRefreshFlowsQuery"],
        });
        queryClient.invalidateQueries({
          queryKey: ["useGetFolders"],
        });
        queryClient.invalidateQueries({
          queryKey: ["useGetFolder"],
        });
        await options?.onSettled?.(...args);
      },
    });

  return mutation;
};
