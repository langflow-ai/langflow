import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IDeleteFile {
  id: string;
}

export const useDeleteFileV2: useMutationFunctionType<
  IDeleteFile,
  void,
  unknown,
  Error
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteFileFn = async (): Promise<unknown> => {
    const response = await api.delete<unknown>(
      `${getURL("FILE_MANAGEMENT", { id: params.id }, true)}`,
    );

    return response.data;
  };

  const mutation: UseMutationResult<unknown, Error, void> = mutate(
    ["useDeleteFileV2"],
    deleteFileFn,
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
