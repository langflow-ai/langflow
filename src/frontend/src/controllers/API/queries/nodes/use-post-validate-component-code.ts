import {
  APIClassType,
  CustomComponentRequest,
  ResponseErrorTypeAPI,
  useMutationFunctionType,
} from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostValidateComponentCode {
  code: string;
  frontend_node: APIClassType;
}

export const usePostValidateComponentCode: useMutationFunctionType<
  undefined,
  IPostValidateComponentCode,
  CustomComponentRequest,
  ResponseErrorTypeAPI
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const postValidateComponentCodeFn = async (
    payload: IPostValidateComponentCode,
  ): Promise<CustomComponentRequest> => {
    const response = await api.post<CustomComponentRequest>(
      getURL("CUSTOM_COMPONENT"),
      {
        code: payload.code,
        frontend_node: payload.frontend_node,
      },
    );

    return response.data;
  };

  const mutation: UseMutationResult<
    CustomComponentRequest,
    ResponseErrorTypeAPI,
    IPostValidateComponentCode
  > = mutate(
    ["usePostValidateComponentCode"],
    postValidateComponentCodeFn,
    options,
  );

  return mutation;
};
