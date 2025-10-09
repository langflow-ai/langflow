import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { UseRequestProcessor } from "../../services/request-processor";

interface ConvertSpecRequest {
  spec_yaml: string;
  variables?: Record<string, any>;
  tweaks?: Record<string, any>;
}

interface ConvertSpecResponse {
  flow: Record<string, any>;
  success: boolean;
}

export const useConvertSpec: useMutationFunctionType<
  ConvertSpecResponse,
  ConvertSpecRequest
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const convertSpecFn = async (
    payload: ConvertSpecRequest
  ): Promise<ConvertSpecResponse> => {
    const response = await api.post(`/api/v1/spec/convert`, {
      spec_yaml: payload.spec_yaml,
      variables: payload.variables || null,
      tweaks: payload.tweaks || null,
    });
    return response.data;
  };

  const mutation: UseMutationResult<
    ConvertSpecResponse,
    any,
    ConvertSpecRequest
  > = mutate(["useConvertSpec"], convertSpecFn, options);

  return mutation;
};
