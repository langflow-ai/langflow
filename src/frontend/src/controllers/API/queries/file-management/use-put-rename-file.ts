import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IPostRenameFile {
  id: string;
  name: string;
}

export const usePostRenameFileV2: useMutationFunctionType<
  undefined,
  IPostRenameFile
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const postRenameFileFn = async (payload: IPostRenameFile): Promise<any> => {
    const response = await api.put<any>(
      `${getURL("FILE_MANAGEMENT", { id: payload.id }, true)}?name=${encodeURI(payload.name)}`,
    );

    return response.data;
  };

  const mutation: UseMutationResult<IPostRenameFile, any, IPostRenameFile> =
    mutate(
      ["usePostRenameFileV2"],
      async (payload: IPostRenameFile) => {
        const res = await postRenameFileFn(payload);
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
