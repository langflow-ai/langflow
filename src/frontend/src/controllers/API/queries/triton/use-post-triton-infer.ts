import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { TritonInferRequest, TritonInferResponse } from "@/types/triton";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface PostTritonInferArgs {
  serverId: string;
  modelName: string;
  body: TritonInferRequest;
}

export const usePostTritonInfer: useMutationFunctionType<
  undefined,
  PostTritonInferArgs,
  TritonInferResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function runInfer({
    serverId,
    modelName,
    body,
  }: PostTritonInferArgs): Promise<TritonInferResponse> {
    const { data } = await api.post<TritonInferResponse>(
      `${getURL("TRITON_SERVERS")}/${serverId}/models/${modelName}/infer`,
      body,
    );
    return data;
  }

  const mutation: UseMutationResult<
    TritonInferResponse,
    Error,
    PostTritonInferArgs
  > = mutate(["usePostTritonInfer"], runInfer, {
    ...options,
  });

  return mutation;
};
