import type { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { getBackendUrl } from "@/config/constants";

interface IUploadPresignedUrlRequest {
  sourceType: string;
  fileName: string;
  sourceDetails: {
    containerName: string;
    storageAccount: string;
  };
}

interface IUploadPresignedUrlResponse {
  presignedUrl: {
    data: {
      signedUrl: string;
    };
    status: string;
  };
}

export const usePostUploadPresignedUrl = (
  options?: any
): UseMutationResult<IUploadPresignedUrlResponse, any, IUploadPresignedUrlRequest> => {
  const { mutate } = UseRequestProcessor();

  const postUploadPresignedUrlFn = async (
    payload: IUploadPresignedUrlRequest
  ): Promise<IUploadPresignedUrlResponse> => {
    const response = await api.post<IUploadPresignedUrlResponse>(
      `${getBackendUrl()}/api/v1/flexstore/signedurl/upload`,
      payload
    );

    return response.data;
  };

  const mutation: UseMutationResult<
    IUploadPresignedUrlResponse,
    any,
    IUploadPresignedUrlRequest
  > = mutate(
    ["usePostUploadPresignedUrl"],
    postUploadPresignedUrlFn,
    options
  );

  return mutation;
};
