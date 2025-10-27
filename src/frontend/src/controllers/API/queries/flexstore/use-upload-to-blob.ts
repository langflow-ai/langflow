import { useMutation } from "@tanstack/react-query";
import type { UseMutationResult, UseMutationOptions } from "@tanstack/react-query";
import axios from "axios";

interface IUploadToBlobRequest {
  presignedUrl: string;
  file: File;
}

export const useUploadToBlob = (
  options?: UseMutationOptions<void, any, IUploadToBlobRequest>
): UseMutationResult<void, any, IUploadToBlobRequest> => {
  return useMutation({
    mutationFn: async ({ presignedUrl, file }: IUploadToBlobRequest) => {
      // Upload directly to Azure blob storage using the presigned URL
      await axios.put(presignedUrl, file, {
        headers: {
          "Content-Type": file.type,
          "x-ms-blob-type": "BlockBlob",
        },
      });
    },
    ...options,
  });
};
