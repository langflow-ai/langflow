import type { UseMutationResult } from "@tanstack/react-query";
import { getFetchCredentials } from "@/customization/utils/get-fetch-credentials";
import type { useMutationFunctionType } from "@/types/api";
import type { FileType } from "@/types/file_management";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DuplicateFileQueryParams {
  id: string;
  filename: string;
  type: string;
}

export const useDuplicateFileV2: useMutationFunctionType<
  DuplicateFileQueryParams,
  void,
  FileType,
  Error
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const duplicateFileFn = async (): Promise<FileType> => {
    // First download the file
    const response = await fetch(
      `${getURL("FILE_MANAGEMENT", { id: params.id }, true)}`,
      {
        headers: {
          Accept: "*/*",
        },
        credentials: getFetchCredentials(),
      },
    );
    const blob = await response.blob();

    // Create a File object from the blob
    const file = new File([blob], params.filename + "." + params.type, {
      type: blob.type,
    });

    // Upload the file
    const formData = new FormData();
    formData.append("file", file);

    const uploadResponse = await api.post<FileType>(
      `${getURL("FILE_MANAGEMENT", {}, true)}/`,
      formData,
    );

    return uploadResponse.data;
  };

  const mutation: UseMutationResult<FileType, Error, void> = mutate(
    ["useDuplicateFileV2"],
    duplicateFileFn,
    {
      onSettled: (...args) => {
        queryClient.invalidateQueries({
          queryKey: ["useGetFilesV2"],
        });
        options?.onSettled?.(...args);
      },
      ...options,
    },
  );

  return mutation;
};
