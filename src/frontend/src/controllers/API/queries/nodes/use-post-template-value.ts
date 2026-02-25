import type { UseMutationResult } from "@tanstack/react-query";
import useFlowStore from "@/stores/flowStore";
import type {
  APIClassType,
  ResponseErrorDetailAPI,
  useMutationFunctionType,
} from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { useTypesStore } from "@/stores/typesStore";

interface IPostTemplateValue {
  value: any;
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

  const postTemplateValueFn = async (
    payload: IPostTemplateValue,
  ): Promise<APIClassType | undefined> => {
    const template = node.template;

    if (!template) return;

    const allowCustomComponents =
      useUtilityStore.getState().allowCustomComponents;

    if (!allowCustomComponents) {
      // Check componentsToUpdate first (fast path)
      const componentsToUpdate = useFlowStore.getState().componentsToUpdate;
      const isOutdated = componentsToUpdate.some(
        (c) => c.id === nodeId && c.outdated && !c.userEdited,
      );
      if (isOutdated) return undefined;

      // Also check code directly against templates (covers race where
      // componentsToUpdate hasn't been populated yet due to templates loading)
      const nodeType =
        useFlowStore.getState().getNode(nodeId)?.data?.type;
      if (nodeType) {
        const templates = useTypesStore.getState().templates;
        const serverCode = templates[nodeType]?.template?.code?.value;
        if (serverCode && serverCode !== template.code?.value) {
          return undefined;
        }
      }
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
      response = await api.post<APIClassType>(
        getURL("CUSTOM_COMPONENT", { update: "update" }),
        {
          code: template.code.value,
          template: preparedTemplate,
          field: parameterId,
          field_value: payload.value,
          tool_mode: payload.tool_mode,
        },
      );
    } catch (e: any) {
      // Suppress 403 from outdated component code when custom components
      // are disabled — this is a fallback for race conditions where the
      // guards above couldn't detect the outdated state in time.
      if (!allowCustomComponents && e?.response?.status === 403) {
        return undefined;
      }
      throw e;
    }

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
