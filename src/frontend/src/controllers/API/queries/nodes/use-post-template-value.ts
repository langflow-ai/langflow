import {
  APIClassType,
  APITemplateType,
  ResponseErrorDetailAPI,
  useMutationFunctionType,
} from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostTemplateValue {
  value: any;
}

interface IPostTemplateValueParams {
  node: APIClassType;
  nodeId: string;
  parameterId: string;
}

export const usePostTemplateValue: useMutationFunctionType<
  IPostTemplateValueParams,
  IPostTemplateValue,
  APITemplateType | undefined,
  ResponseErrorDetailAPI
> = ({ parameterId, nodeId, node }, options?) => {
  const { mutate } = UseRequestProcessor();

  const postTemplateValueFn = async (
    payload: IPostTemplateValue,
  ): Promise<APITemplateType | undefined> => {
    const template = node.template;

    if (!template) return;

    const response = await api.post<APIClassType>(
      getURL("CUSTOM_COMPONENT", { update: "update" }),
      {
        code: template.code.value,
        template: template,
        field: parameterId,
        field_value: payload.value,
      },
    );

    return response.data.template;
  };

  const mutation: UseMutationResult<
    APITemplateType | undefined,
    ResponseErrorDetailAPI,
    IPostTemplateValue
  > = mutate(
    ["usePostTemplateValue", { parameterId, nodeId }],
    postTemplateValueFn,
    options,
  );

  return mutation;
};
