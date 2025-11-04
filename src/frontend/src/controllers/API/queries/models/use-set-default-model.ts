import { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseMutationResult } from "@tanstack/react-query";
import { UseRequestProcessor } from "../../services/request-processor";

export interface SetDefaultModelRequest {
  model_name: string;
  provider: string;
  model_type: string;
}

export interface SetDefaultModelResponse {
  default_model: {
    model_name: string;
    provider: string;
    model_type: string;
  };
}

export const useSetDefaultModel: useMutationFunctionType<
  SetDefaultModelRequest,
  SetDefaultModelResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const setDefaultModelFn = async (
    data: SetDefaultModelRequest,
  ): Promise<SetDefaultModelResponse> => {
    const response = await api.post<SetDefaultModelResponse>(
      `${getURL("MODELS")}/default_model`,
      data,
    );
    return response.data;
  };

  const mutation: UseMutationResult<
    SetDefaultModelResponse,
    any,
    SetDefaultModelRequest
  > = mutate(["useSetDefaultModel"], setDefaultModelFn, options);

  return mutation;
};
