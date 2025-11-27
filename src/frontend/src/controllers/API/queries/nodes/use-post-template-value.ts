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
    const preparedTemplate = {
      ...template,
      ...(flowId ? { _frontend_node_flow_id: { value: flowId } } : {}),
      ...(folderId ? { _frontend_node_folder_id: { value: folderId } } : {}),
      is_refresh: payload.is_refresh,
    };
    const lastUpdated = new Date().toISOString();
    const response = await api.post<APIClassType>(
      getURL("CUSTOM_COMPONENT", { update: "update" }),
      {
        code: template.code.value,
        template: preparedTemplate,
        field: parameterId,
        field_value: payload.value,
        tool_mode: payload.tool_mode,
      },
    );
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
