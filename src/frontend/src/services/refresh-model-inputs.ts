import type { QueryClient } from "@tanstack/react-query";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { appendProviderScope } from "@/controllers/API/helpers/provider-scope";
import {
  getModelProvidersQueryOptions,
  type ModelProviderWithStatus,
} from "@/controllers/API/queries/models/use-get-model-providers";
import useAlertStore from "@/stores/alertStore";
import useFlowStore, { syncNodeTranslations } from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { APIClassType } from "@/types/api";
import type { AllNodeType } from "@/types/flow";
import {
  isCustomComponentBlockError,
  isNodeOutdated,
} from "@/utils/customComponentGuards";
import {
  buildRefreshPayload,
  createUpdatedNode,
  findModelFieldKey,
  isModelNode,
  validateModelValue,
} from "@/utils/model-node-helpers";
import i18n from "../i18n";

export interface RefreshOptions {
  silent?: boolean;
}

type ProviderConfiguration = ReadonlyMap<string, boolean>;

// Prevents concurrent refresh operations; queues the latest request if busy
let isRefreshInProgress = false;
let pendingRefresh: {
  queryClient?: QueryClient;
  options?: RefreshOptions;
} | null = null;

/** Refreshes all model input components in the current flow */
export async function refreshAllModelInputs(
  queryClient?: QueryClient,
  options?: RefreshOptions,
): Promise<void> {
  if (isRefreshInProgress) {
    // Queue the latest request so it runs after the current one finishes
    pendingRefresh = { queryClient, options };
    return;
  }
  isRefreshInProgress = true;

  const { setSuccessData, setErrorData } = useAlertStore.getState();
  const showNotifications = !options?.silent;

  try {
    const allNodes = useFlowStore.getState().nodes;
    const setNode = useFlowStore.getState().setNode;
    const flowId = useFlowsManagerStore.getState().currentFlowId;
    const folderId = useFlowsManagerStore.getState().currentFlow?.folder_id;

    if (queryClient) {
      await queryClient.invalidateQueries({
        queryKey: ["useGetModelProviders"],
      });
      await queryClient.invalidateQueries({
        queryKey: ["useGetEnabledModels"],
      });
      await queryClient.invalidateQueries({
        queryKey: ["useGetProviderVariables"],
      });
    }

    const nodesWithModelFields = allNodes.filter(isModelNode);

    if (nodesWithModelFields.length === 0) {
      if (showNotifications) {
        // biome-ignore lint/suspicious/noExplicitAny: legacy
        setSuccessData({ title: (i18n as any).t("errors.noModelsToRefresh") });
      }
      return;
    }

    let providerConfiguration: ProviderConfiguration | undefined;
    if (queryClient) {
      try {
        const providers = await queryClient.fetchQuery(
          getModelProvidersQueryOptions({ flowId, purpose: "configure" }),
        );
        providerConfiguration = buildProviderConfiguration(providers);
      } catch {
        // A failed refetch may leave stale catalog data in React Query. Treat
        // provider status as unknown so refresh never overwrites a saved model.
        providerConfiguration = undefined;
      }
    }

    const refreshTasks = nodesWithModelFields.map((node) =>
      refreshSingleNode(node, flowId, folderId, setNode, providerConfiguration),
    );
    await Promise.all(refreshTasks);

    // Re-apply translations after refresh overwrites output display_names
    syncNodeTranslations();

    if (showNotifications) {
      const count = nodesWithModelFields.length;
      setSuccessData({
        // biome-ignore lint/suspicious/noExplicitAny: legacy
        title: (i18n as any).t("alerts.modelsRefreshed", { count }),
      });
    }
  } catch (error) {
    console.error("Error refreshing model inputs:", error);
    if (showNotifications) {
      setErrorData({
        // biome-ignore lint/suspicious/noExplicitAny: legacy
        title: (i18n as any).t("errors.refreshingModels"),
        list: [(error as Error)?.message || "An unexpected error occurred"],
      });
    }
  } finally {
    isRefreshInProgress = false;
    // If another refresh was requested while this one was running, run it now
    if (pendingRefresh) {
      const { queryClient: qc, options: opts } = pendingRefresh;
      pendingRefresh = null;
      await refreshAllModelInputs(qc, opts);
    }
  }
}

function buildProviderConfiguration(
  providers: ModelProviderWithStatus[],
): ProviderConfiguration {
  return new Map(
    providers.flatMap((provider) =>
      typeof provider.is_configured === "boolean"
        ? [[provider.provider, provider.is_configured] as const]
        : [],
    ),
  );
}

/** Refreshes a single node's model field via API */
async function refreshSingleNode(
  node: AllNodeType,
  flowId: string | undefined,
  folderId: string | undefined,
  setNode: ReturnType<typeof useFlowStore.getState>["setNode"],
  providerConfiguration?: ProviderConfiguration,
): Promise<void> {
  const nodeData = node.data?.node as APIClassType | undefined;
  if (!nodeData?.template) return;

  const modelFieldKey = findModelFieldKey(nodeData.template);
  if (!modelFieldKey) return;

  // Skip refresh for outdated components when custom components are not allowed
  // (the old code would be rejected by the backend with 403)
  const allowCustomComponents =
    useUtilityStore.getState().allowCustomComponents;
  if (
    !allowCustomComponents &&
    isNodeOutdated(node.id, nodeData.template.code?.value)
  ) {
    return;
  }

  const currentModelValue = nodeData.template[modelFieldKey]?.value;

  try {
    const requestPayload = buildRefreshPayload(
      nodeData.template,
      flowId,
      folderId,
    );

    let response;
    try {
      const queryParams = new URLSearchParams();
      appendProviderScope(queryParams, { flowId });
      response = await api.post<APIClassType>(
        `${getURL("CUSTOM_COMPONENT", { update: "update" })}${
          queryParams.toString() ? `?${queryParams.toString()}` : ""
        }`,
        {
          code: nodeData.template.code?.value,
          template: requestPayload,
          field: modelFieldKey,
          field_value: currentModelValue,
          tool_mode: nodeData.tool_mode,
        },
      );
      // biome-ignore lint/suspicious/noExplicitAny: legacy
    } catch (e: any) {
      // Suppress 403 specifically from custom component blocking — fallback
      // for race conditions where guards above couldn't detect the outdated
      // state.
      if (!allowCustomComponents && isCustomComponentBlockError(e)) {
        console.warn(
          `Suppressed 403 for outdated component (node ${node.id}):`,
          e.response.data.detail,
        );
        return;
      }
      throw e;
    }

    const responseData = response.data;
    if (!responseData?.template) return;

    // Validate and correct the model value against available options
    const validatedTemplate = validateModelValue(
      responseData.template,
      modelFieldKey,
      providerConfiguration,
    );

    // This response was authorized for the flow/project snapshot captured at
    // refresh start. Never let it update a same-id node after navigation (or a
    // project move) changes the active scope while the request is in flight.
    const activeFlow = useFlowsManagerStore.getState();
    if (
      activeFlow.currentFlowId !== flowId ||
      activeFlow.currentFlow?.folder_id !== folderId
    ) {
      return;
    }

    setNode(
      node.id,
      (currentNode) =>
        createUpdatedNode(currentNode, validatedTemplate, responseData.outputs),
      false,
    );
  } catch (error) {
    console.warn(`Failed to refresh model node ${node.id}:`, error);
  }
}
