import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostUploadFile {
  file: File;
}

export const usePostUploadFileV2: useMutationFunctionType<
  undefined,
  IPostUploadFile
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const postUploadFileFn = async (payload: IPostUploadFile): Promise<any> => {
    const formData = new FormData();
    formData.append("file", payload.file);

    const response = await api.post<any>(
      `${getURL("FILE_MANAGEMENT", {}, true)}/`,
      formData,
    );

    return response.data;
  };

  const mutation: UseMutationResult<IPostUploadFile, any, IPostUploadFile> =
    mutate(
      ["usePostUploadFileV2"],
      async (payload: IPostUploadFile) => {
        const res = await postUploadFileFn(payload);
        return res;
      },
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
