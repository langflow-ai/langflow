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
  CustomComponentRequest | undefined,
  ResponseErrorTypeAPI
> = (options?) => {
  const { mutate } = UseRequestProcessor();
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

  const postValidateComponentCodeFn = async (
    payload: IPostValidateComponentCode,
  ): Promise<CustomComponentRequest | undefined> => {
    if (!capturedScopeIsCurrent()) return undefined;

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

    // Validation output may contain provider-derived fields. Discard it when
    // navigation or a project move invalidates the scope that authorized it.
    if (!capturedScopeIsCurrent()) return undefined;

    return response.data;
  };

  const mutation: UseMutationResult<
    CustomComponentRequest | undefined,
    ResponseErrorTypeAPI,
    IPostValidateComponentCode
  > = mutate(["usePostValidateComponentCode"], postValidateComponentCodeFn, {
    ...options,
    retry: 0,
    retryDelay: 0,
  });

  return mutation;
};
