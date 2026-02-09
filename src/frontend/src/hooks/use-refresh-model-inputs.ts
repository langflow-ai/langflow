import { QueryClient, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef } from "react";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type {
  APIClassType,
  APITemplateType,
  ModelOptionType,
} from "@/types/api";
import type { AllNodeType } from "@/types/flow";

export interface RefreshOptions {
  silent?: boolean;
}

// Prevents concurrent refresh operations
let isRefreshInProgress = false;

/** Checks if a node has a model-type input field */
export function isModelNode(node: AllNodeType): boolean {
  if (node.type !== "genericNode") return false;
  const template = node.data?.node?.template;
  if (!template) return false;

  return Object.values(template).some((field: any) => field?.type === "model");
}

/** Finds the model field key in a template */
export function findModelFieldKey(
  template: APITemplateType,
): string | undefined {
  return Object.keys(template).find((key) => template[key]?.type === "model");
}

/** Builds the refresh API payload with flow context */
export function buildRefreshPayload(
  template: APITemplateType,
  flowId: string | undefined,
  folderId: string | undefined,
): Record<string, any> {
  return {
    ...template,
    ...(flowId && { _frontend_node_flow_id: { value: flowId } }),
    ...(folderId && { _frontend_node_folder_id: { value: folderId } }),
    is_refresh: true,
  };
}

/** Creates an updated node with new template data */
export function createUpdatedNode(
  currentNode: AllNodeType,
  updatedTemplate: APITemplateType,
  updatedOutputs?: APIClassType["outputs"],
): AllNodeType {
  return {
    ...currentNode,
    data: {
      ...currentNode.data,
      node: {
        ...currentNode.data.node,
        template: updatedTemplate,
        outputs: updatedOutputs ?? currentNode.data.node.outputs,
      },
    },
  };
}

/** Refreshes all model input components in the current flow */
export async function refreshAllModelInputs(
  queryClient?: QueryClient,
  options?: RefreshOptions,
): Promise<void> {
  if (isRefreshInProgress) return;
  isRefreshInProgress = true;

  const { setSuccessData, setErrorData } = useAlertStore.getState();
  const showNotifications = !options?.silent;

  try {
    const allNodes = useFlowStore.getState().nodes;
    const setNode = useFlowStore.getState().setNode;
    const flowId = useFlowsManagerStore.getState().currentFlowId;
    const folderId = useFlowsManagerStore.getState().currentFlow?.folder_id;

    if (queryClient) {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["useGetModelProviders"] }),
        queryClient.invalidateQueries({ queryKey: ["useGetEnabledModels"] }),
      ]);
    }

    const nodesWithModelFields = allNodes.filter(isModelNode);

    if (nodesWithModelFields.length === 0) {
      if (showNotifications) {
        setSuccessData({ title: "No model components to refresh" });
      }
      return;
    }

    const refreshTasks = nodesWithModelFields.map((node) =>
      refreshSingleNode(node, flowId, folderId, setNode),
    );
    await Promise.all(refreshTasks);

    if (showNotifications) {
      const count = nodesWithModelFields.length;
      const plural = count > 1 ? "s" : "";
      setSuccessData({ title: `Refreshed ${count} model component${plural}` });
    }
  } catch (error) {
    console.error("Error refreshing model inputs:", error);
    if (showNotifications) {
      setErrorData({
        title: "Error refreshing model components",
        list: [(error as Error)?.message || "An unexpected error occurred"],
      });
    }
  } finally {
    isRefreshInProgress = false;
  }
}

/** Validates and corrects model value against available options */
function validateModelValue(
  template: APITemplateType,
  modelFieldKey: string,
): APITemplateType {
  const modelField = template[modelFieldKey];
  if (!modelField) return template;

  const options = modelField.options || [];
  const currentValue = modelField.value;

  // Filter out disabled provider placeholders to get actual available models
  const availableOptions = options.filter(
    (opt: ModelOptionType) => !opt?.metadata?.is_disabled_provider,
  );

  // Get current model name from value
  const currentModelName = Array.isArray(currentValue)
    ? currentValue[0]?.name
    : currentValue?.name;

  // Check if current model is still available
  const isCurrentModelValid =
    currentModelName &&
    availableOptions.some(
      (opt: ModelOptionType) => opt.name === currentModelName,
    );

  if (isCurrentModelValid) {
    // Current value is valid, no changes needed
    return template;
  }

  // Current value is invalid - need to update it
  if (availableOptions.length > 0) {
    // Select the first available model
    const firstOption = availableOptions[0];
    const newValue = [
      {
        ...(firstOption.id && { id: firstOption.id }),
        name: firstOption.name,
        icon: firstOption.icon || "Bot",
        provider: firstOption.provider || "Unknown",
        metadata: firstOption.metadata ?? {},
      },
    ];
    return {
      ...template,
      [modelFieldKey]: {
        ...modelField,
        value: newValue,
      },
    };
  }

  // No available options - clear the value
  return {
    ...template,
    [modelFieldKey]: {
      ...modelField,
      value: [],
    },
  };
}

/** Refreshes a single node's model field via API */
async function refreshSingleNode(
  node: AllNodeType,
  flowId: string | undefined,
  folderId: string | undefined,
  setNode: ReturnType<typeof useFlowStore.getState>["setNode"],
): Promise<void> {
  const nodeData = node.data?.node as APIClassType | undefined;
  if (!nodeData?.template) return;

  const modelFieldKey = findModelFieldKey(nodeData.template);
  if (!modelFieldKey) return;

  const currentModelValue = nodeData.template[modelFieldKey]?.value;

  try {
    const requestPayload = buildRefreshPayload(
      nodeData.template,
      flowId,
      folderId,
    );

    const response = await api.post<APIClassType>(
      getURL("CUSTOM_COMPONENT", { update: "update" }),
      {
        code: nodeData.template.code?.value,
        template: requestPayload,
        field: modelFieldKey,
        field_value: currentModelValue,
        tool_mode: nodeData.tool_mode,
      },
    );

    const responseData = response.data;
    if (!responseData?.template) return;

    // Validate and correct the model value against available options
    const validatedTemplate = validateModelValue(
      responseData.template,
      modelFieldKey,
    );

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

/** Hook to refresh all model inputs in the current flow */
export function useRefreshModelInputs() {
  const queryClient = useQueryClient();
  const isRefreshingRef = useRef(false);

  const refresh = useCallback(
    async (options?: RefreshOptions) => {
      if (isRefreshingRef.current) return;
      isRefreshingRef.current = true;

      try {
        await refreshAllModelInputs(queryClient, options);
      } finally {
        isRefreshingRef.current = false;
      }
    },
    [queryClient],
  );

  return {
    refresh,
    refreshAllModelInputs: refresh, // deprecated alias
  };
}
