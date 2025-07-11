import type { useMutationFunctionType } from "@/types/api";
import type { UseMutationResult } from "@tanstack/react-query";
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
  void
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const duplicateFileFn = async (): Promise<any> => {
    // First download the file
    const response = await fetch(
      `${getURL("FILE_MANAGEMENT", { id: params.id }, true)}`,
      {
        headers: {
          Accept: "*/*",
        },
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

    const uploadResponse = await api.post<any>(
      `${getURL("FILE_MANAGEMENT", {}, true)}/`,
      formData,
    );

    return uploadResponse.data;
  };

  const mutation: UseMutationResult<any, any, void> = mutate(
    ["useDuplicateFileV2"],
    duplicateFileFn,
    {
      onSettled: (data, error, variables, context) => {
        queryClient.invalidateQueries({
          queryKey: ["useGetFilesV2"],
        });
        options?.onSettled?.(data, error, variables, context);
      },
      ...options,
    },
  );

  return mutation;
};
