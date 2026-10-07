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
  IPostRenameFile,
  IPostRenameFile,
  Error
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const postRenameFileFn = async (
    payload: IPostRenameFile,
  ): Promise<IPostRenameFile> => {
    const response = await api.put<IPostRenameFile>(
      `${getURL("FILE_MANAGEMENT", { id: payload.id }, true)}?name=${encodeURI(payload.name)}`,
    );

    return response.data;
  };

  const mutation: UseMutationResult<IPostRenameFile, Error, IPostRenameFile> =
    mutate(
      ["usePostRenameFileV2"],
      async (payload: IPostRenameFile) => {
        const res = await postRenameFileFn(payload);
        return res;
      },
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
