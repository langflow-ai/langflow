import { SAVE_DEBOUNCE_TIME } from "@/constants/constants";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { APIClassType, useMutationFunctionType } from "@/types/api";
import { NodeDataType } from "@/types/flow";
import { UseMutationResult } from "@tanstack/react-query";
import { cloneDeep, debounce } from "lodash";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostTemplateValue {
  value: any;
  load_from_db?: boolean;
  skipSnapshot?: boolean;
}

interface IPostTemplateValueParams {
  nodeData: NodeDataType;
  parameterId: string;
}

export const usePostTemplateValue: useMutationFunctionType<
  IPostTemplateValueParams,
  IPostTemplateValue
> = ({ parameterId, nodeData }, options?) => {
  const { mutate } = UseRequestProcessor();

  const postTemplateValueFn = async (
    payload: IPostTemplateValue,
  ): Promise<NodeDataType | undefined> => {
    const takeSnapshot = useFlowsManagerStore.getState().takeSnapshot;
    const setNode = useFlowStore.getState().setNode;
    const template = nodeData.node?.template;

    if (!template) throw new Error("Template not found in node");

    const parameter = template[parameterId];

    if (!parameter) throw new Error("Parameter not found in the template");

    if (JSON.stringify(parameter.value) === JSON.stringify(payload.value))
      return;

    if (!payload.skipSnapshot) takeSnapshot();

    const shouldUpdate =
      parameter.real_time_refresh && !parameter.refresh_button;

    parameter.value = payload.value;

    if (payload.load_from_db !== undefined) {
      parameter.load_from_db = payload.load_from_db;
    }

    if (shouldUpdate) {
      const response = await api.post<APIClassType>(
        getURL("CUSTOM_COMPONENT", { update: "update" }),
        {
          code: template.code.value,
          template: template,
          field: parameterId,
          field_value: payload.value,
        },
      );
      nodeData.node!.template = response.data.template;
    }

    setNode(nodeData.id, (oldNode) => ({
      ...oldNode,
      data: cloneDeep(nodeData),
    }));

    return nodeData;
  };

  const mutation: UseMutationResult<
    IPostTemplateValue,
    any,
    IPostTemplateValue
  > = mutate(["usePostTemplateValue"], postTemplateValueFn, options);

  return mutation;
};
