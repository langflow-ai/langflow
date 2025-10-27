import type { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { getBackendUrl } from "@/config/constants";

interface IReadPresignedUrlRequest {
  sourceType: string;
  fileName: string;
  sourceDetails: {
    containerName: string;
    storageAccount: string;
  };
}

interface IReadPresignedUrlResponse {
  presignedUrl: {
    data: {
      signedUrl: string;
    };
    status: string;
  };
}

export const usePostReadPresignedUrl = (
  options?: any
): UseMutationResult<IReadPresignedUrlResponse, any, IReadPresignedUrlRequest> => {
  const { mutate } = UseRequestProcessor();

  const postReadPresignedUrlFn = async (
    payload: IReadPresignedUrlRequest
  ): Promise<IReadPresignedUrlResponse> => {
    const response = await api.post<IReadPresignedUrlResponse>(
      `${getBackendUrl()}/api/v1/flexstore/signedurl/read`,
      payload
    );

    return response.data;
  };

  const mutation: UseMutationResult<
    IReadPresignedUrlResponse,
    any,
    IReadPresignedUrlRequest
  > = mutate(
    ["usePostReadPresignedUrl"],
    postReadPresignedUrlFn,
    options
  );

  return mutation;
};
