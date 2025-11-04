import { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseMutationResult } from "@tanstack/react-query";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ClearDefaultModelRequest {
  model_type: string;
}

export interface ClearDefaultModelResponse {
  default_model: null;
}

export const useClearDefaultModel: useMutationFunctionType<
  ClearDefaultModelRequest,
  ClearDefaultModelResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const clearDefaultModelFn = async (
    data: ClearDefaultModelRequest,
  ): Promise<ClearDefaultModelResponse> => {
    const response = await api.delete<ClearDefaultModelResponse>(
      `${getURL("MODELS")}/default_model?model_type=${data.model_type}`,
    );
    return response.data;
  };

  const mutation: UseMutationResult<
    ClearDefaultModelResponse,
    any,
    ClearDefaultModelRequest
  > = mutate(["useClearDefaultModel"], clearDefaultModelFn, options);

  return mutation;
};
