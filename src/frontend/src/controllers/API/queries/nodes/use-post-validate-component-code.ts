import type { UseMutationResult } from "@tanstack/react-query";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type {
  APIClassType,
  CustomComponentRequest,
  ResponseErrorTypeAPI,
  useMutationFunctionType,
} from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { appendProviderScope } from "../../helpers/provider-scope";
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
  const flowId = useFlowsManagerStore((state) => state.currentFlowId);

  const postValidateComponentCodeFn = async (
    payload: IPostValidateComponentCode,
  ): Promise<CustomComponentRequest> => {
    const queryParams = new URLSearchParams();
    appendProviderScope(queryParams, { flowId });
    const response = await api.post<CustomComponentRequest>(
      `${getURL("CUSTOM_COMPONENT")}${
        queryParams.toString() ? `?${queryParams.toString()}` : ""
      }`,
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
  > = mutate(["usePostValidateComponentCode"], postValidateComponentCodeFn, {
    ...options,
    retry: 0,
    retryDelay: 0,
  });

  return mutation;
};
