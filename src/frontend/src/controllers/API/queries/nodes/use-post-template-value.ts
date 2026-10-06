import type { UseMutationResult } from "@tanstack/react-query";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type {
  APIClassType,
  ResponseErrorDetailAPI,
  useMutationFunctionType,
} from "@/types/api";
import {
  isCustomComponentBlockError,
  isNodeOutdated,
} from "@/utils/customComponentGuards";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { appendProviderScope } from "../../helpers/provider-scope";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostTemplateValue {
  value: unknown;
  // A discrete edit can run before this hook re-renders, so prefer the
  // caller's mutated template over the node snapshot captured by the hook.
  template?: APIClassType["template"];
  tool_mode?: boolean;
  // the dropdown input re-gathers all
  // dropdown items each time a single
  // single item is selected,
  // which is computationally expensive for the backend.
  // to avoid this, we add an explicit flag
  // to indicate whether the refresh button was pressed.
  // TODO: this is a hack and should be removed when we have a better solution.
  is_refresh?: boolean;
}

interface IPostTemplateValueParams {
  node: APIClassType;
  nodeId: string;
  parameterId: string;
}

export const usePostTemplateValue: useMutationFunctionType<
  IPostTemplateValueParams,
  IPostTemplateValue,
  APIClassType,
  ResponseErrorDetailAPI
> = ({ parameterId, nodeId, node }, options?) => {
  const { mutate } = UseRequestProcessor();
  const getNode = useFlowStore((state) => state.getNode);
  const flowId = useFlowsManagerStore((state) => state.currentFlowId);
  const folderId = useFlowsManagerStore(
    (state) => state.currentFlow?.folder_id,
  );

  const capturedScopeIsCurrent = (): boolean => {
    const current = useFlowsManagerStore.getState();
    return (
      current.currentFlowId === flowId &&
      current.currentFlow?.folder_id === folderId
    );
  };

  const postTemplateValueFn = async (
    payload: IPostTemplateValue,
  ): Promise<APIClassType | undefined> => {
    // The hook may remain mounted briefly after navigation. Do not issue an
    // edit under the flow/project scope captured by a previous render.
    if (!capturedScopeIsCurrent()) return undefined;

    const template = payload.template ?? node.template;

    if (!template) return;

    // LE-2045: a grouped node proxies its fields and has no code to recompile.
    if (!template.code) return undefined;

    const allowCustomComponents =
      useUtilityStore.getState().allowCustomComponents;

    if (
      !allowCustomComponents &&
      isNodeOutdated(nodeId, template.code?.value)
    ) {
      return undefined;
    }

    const preparedTemplate = {
      ...template,
      ...(flowId ? { _frontend_node_flow_id: { value: flowId } } : {}),
      ...(folderId ? { _frontend_node_folder_id: { value: folderId } } : {}),
      is_refresh: payload.is_refresh,
    };
    const lastUpdated = new Date().toISOString();

    let response;
    try {
      const queryParams = new URLSearchParams();
      appendProviderScope(queryParams, { flowId });
      response = await api.post<APIClassType>(
        `${getURL("CUSTOM_COMPONENT", { update: "update" })}${
          queryParams.toString() ? `?${queryParams.toString()}` : ""
        }`,
        {
          code: template.code.value,
          template: preparedTemplate,
          field: parameterId,
          field_value: payload.value,
          tool_mode: payload.tool_mode,
        },
      );
    } catch (e: unknown) {
      // Suppress 403 specifically from custom component blocking — fallback
      // for race conditions where the guards above couldn't detect the
      // outdated state in time.
      if (!allowCustomComponents && isCustomComponentBlockError(e)) {
        const error = e as ResponseErrorDetailAPI;
        console.warn(
          `Suppressed 403 for outdated component (node ${nodeId}):`,
          error.response.data.detail,
        );
        return undefined;
      }
      throw e;
    }

    // The response is authorized only for the captured scope. A same-id node
    // in the newly active flow must never receive this template.
    if (!capturedScopeIsCurrent()) return undefined;

    const newTemplate = response.data;
    newTemplate.last_updated = lastUpdated;
    const newNode = getNode(nodeId)?.data?.node as APIClassType | undefined;

    if (
      !newNode?.last_updated ||
      !newTemplate.last_updated ||
      Date.parse(newNode.last_updated) < Date.parse(newTemplate.last_updated)
    ) {
      return newTemplate;
    }

    return undefined;
  };

  const mutation: UseMutationResult<
    APIClassType,
    ResponseErrorDetailAPI,
    IPostTemplateValue
  > = mutate(
    ["usePostTemplateValue", { parameterId, nodeId }],
    postTemplateValueFn,
    {
      ...options,
      retry: 0,
    },
  );

  return mutation;
};
