import { UseMutationOptions, useMutation } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import {
  appendProviderScope,
  type ProviderScopeParams,
} from "../../helpers/provider-scope";

export interface ValidateProviderRequest extends ProviderScopeParams {
  provider: string;
  variables: Record<string, string>;
}

export interface ValidateProviderResponse {
  valid: boolean;
  error: string | null;
}

export const useValidateProvider = (
  options?: Omit<
    UseMutationOptions<
      ValidateProviderResponse,
      Error,
      ValidateProviderRequest
    >,
    "mutationFn"
  >,
) => {
  return useMutation<ValidateProviderResponse, Error, ValidateProviderRequest>({
    mutationFn: async ({ flowId, projectId, ...request }) => {
      const queryParams = new URLSearchParams();
      appendProviderScope(queryParams, { flowId, projectId });
      const response = await api.post<ValidateProviderResponse>(
        `${getURL("MODELS")}/validate-provider${
          queryParams.toString() ? `?${queryParams.toString()}` : ""
        }`,
        request,
      );
      return response.data;
    },
    retry: 0,
    ...options,
  });
};
