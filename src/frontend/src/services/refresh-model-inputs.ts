import type { QueryClient } from "@tanstack/react-query";
import { isEqual, isEqualWith, mapValues, omit } from "lodash";
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
import { recordLoadRefresh } from "@/utils/load-refreshes";
import {
  buildRefreshPayload,
  createUpdatedNode,
  findModelFieldKeys,
  isModelNode,
  validateModelValue,
} from "@/utils/model-node-helpers";
import i18n from "../i18n";

export interface RefreshOptions {
  silent?: boolean;
  /** "load" when nobody asked for it: what it rewrites is not credited to a person in a conflict. */
  origin?: "load";
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
      refreshSingleNode(
        node,
        flowId,
        folderId,
        setNode,
        providerConfiguration,
        options?.origin,
      ),
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

// The template serves an unset model as "" while the store normalizes it to [].
const isEmptyModelValue = (value: unknown): boolean =>
  value === undefined ||
  value === null ||
  value === "" ||
  (Array.isArray(value) && value.length === 0);

// isEqualWith customizer: undefined defers to the default comparison.
const sameEmptyValue = (left: unknown, right: unknown): true | undefined =>
  isEmptyModelValue(left) && isEmptyModelValue(right) ? true : undefined;

const fieldPresentation = ["display_name", "info", "placeholder"] as const;
const outputPresentation = ["display_name", "info"] as const;

function refreshState(node: APIClassType | undefined) {
  return {
    // Field-mount requests populate options and provider-field visibility.
    // Flow/project identity is checked separately against the captured scope.
    template: mapValues(
      omit(node?.template, [
        "_frontend_node_flow_id",
        "_frontend_node_folder_id",
      ]),
      (field) =>
        field && typeof field === "object"
          ? omit(field, [
              ...fieldPresentation,
              "options",
              ...(field.type === "model" ? [] : ["show"]),
            ])
          : field,
    ),
    outputs: node?.outputs?.map((output) => omit(output, outputPresentation)),
  };
}

function preservePresentationEdits<T extends object>(
  before: T | undefined,
  current: T | undefined,
  next: T,
  keys: readonly (keyof T)[],
): T {
  if (!before || !current) return next;
  return {
    ...next,
    ...Object.fromEntries(
      keys
        .filter((key) => !isEqual(before[key], current[key]))
        .map((key) => [key, current[key]]),
    ),
  };
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

/** Refreshes every shown model field of a node via API */
async function refreshSingleNode(
  node: AllNodeType,
  flowId: string | undefined,
  folderId: string | undefined,
  setNode: ReturnType<typeof useFlowStore.getState>["setNode"],
  providerConfiguration?: ProviderConfiguration,
  origin?: RefreshOptions["origin"],
): Promise<void> {
  const nodeData = node.data?.node as APIClassType | undefined;
  if (!nodeData?.template) return;

  const modelFieldKeys = findModelFieldKeys(nodeData.template);
  if (modelFieldKeys.length === 0) return;

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

  try {
    // One request per shown model field, in turn: each response is the whole
    // template, so the next field refreshes on top of the previous result.
    let refreshedTemplate = nodeData.template;
    let refreshedOutputs: APIClassType["outputs"] | undefined;
    for (const modelFieldKey of modelFieldKeys) {
      const requestPayload = buildRefreshPayload(
        refreshedTemplate,
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
            frontend_node: { metadata: nodeData.metadata },
            template: requestPayload,
            field: modelFieldKey,
            field_value: refreshedTemplate[modelFieldKey]?.value,
            tool_mode: nodeData.tool_mode,
          },
        );
        // biome-ignore lint/suspicious/noExplicitAny: legacy
      } catch (e: any) {
        // Fallback 403 suppression for races the outdated-state guards above miss.
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
      refreshedTemplate = validateModelValue(
        responseData.template,
        modelFieldKey,
        providerConfiguration,
      );
      refreshedOutputs = responseData.outputs;
    }

    // Authorized for the flow/project scope captured at refresh start; a
    // navigation or project move while in flight must not reach a same-id node.
    const activeFlow = useFlowsManagerStore.getState();
    if (
      activeFlow.currentFlowId !== flowId ||
      activeFlow.currentFlow?.folder_id !== folderId
    ) {
      return;
    }

    // An edit made in flight is newer: a model pick, a mode switch, or a
    // Decision Type change that replaces the outputs. The response carries the
    // template and outputs the request started from and would undo it.
    const liveNode = useFlowStore
      .getState()
      .nodes.find((candidate) => candidate.id === node.id)?.data?.node as
      | APIClassType
      | undefined;
    // Palette hydration translates presentation metadata while a refresh is pending.
    const changedInFlight = !isEqualWith(
      refreshState(liveNode),
      refreshState(nodeData),
      sameEmptyValue,
    );
    if (changedInFlight) return;

    refreshedTemplate = mapValues(refreshedTemplate, (field, key) =>
      field && typeof field === "object"
        ? preservePresentationEdits(
            nodeData.template[key],
            liveNode?.template[key],
            field,
            fieldPresentation,
          )
        : field,
    );
    refreshedOutputs = refreshedOutputs?.map((output) =>
      preservePresentationEdits(
        nodeData.outputs?.find((previous) => previous.name === output.name),
        liveNode?.outputs?.find((current) => current.name === output.name),
        output,
        outputPresentation,
      ),
    );

    // Runs on every flow open, so the user has not asked for this write.
    setNode(
      node.id,
      (currentNode) =>
        createUpdatedNode(currentNode, refreshedTemplate, refreshedOutputs),
      false,
      undefined,
      { autoSave: false },
    );
    if (origin === "load") {
      recordLoadRefresh(flowId, node.id, nodeData.template, refreshedTemplate);
    }
  } catch (error) {
    console.warn(`Failed to refresh model node ${node.id}:`, error);
  }
}
