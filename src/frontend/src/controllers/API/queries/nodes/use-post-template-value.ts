import {
  APIClassType,
  ResponseErrorDetailAPI,
  useMutationFunctionType,
} from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostTemplateValue {
  value: any;
  tool_mode?: boolean;
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

  const postTemplateValueFn = async (
    payload: IPostTemplateValue,
  ): Promise<APIClassType | undefined> => {
    const template = node.template;

    if (!template) return;
    const response = await api.post<APIClassType>(
      getURL("CUSTOM_COMPONENT", { update: "update" }),
      {
        code: template.code.value,
        template: template,
        field: parameterId,
        field_value: payload.value,
        tool_mode: payload.tool_mode,
      },
    );

    return response.data;
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
