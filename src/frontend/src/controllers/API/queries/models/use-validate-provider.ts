import { UseMutationOptions, useMutation } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";

export interface ValidateProviderRequest {
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
    mutationFn: async (request: ValidateProviderRequest) => {
      const response = await api.post<ValidateProviderResponse>(
        `${getURL("MODELS")}/validate-provider`,
        request,
      );
      return response.data;
    },
    retry: 0,
    ...options,
  });
};
