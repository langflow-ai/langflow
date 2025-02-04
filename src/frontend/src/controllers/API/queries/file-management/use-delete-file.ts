import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IDeleteFile {
  id: string;
}

export const useDeleteFileV2: useMutationFunctionType<
  undefined,
  IDeleteFile
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteFileFn = async (payload: IDeleteFile): Promise<any> => {
    const response = await api.delete<any>(
      `${getURL("FILE_MANAGEMENT")}/${payload.id}`,
    );

    return response.data;
  };

  const mutation: UseMutationResult<IDeleteFile, any, IDeleteFile> = mutate(
    ["useDeleteFileV2"],
    async (payload: IDeleteFile) => {
      const res = await deleteFileFn(payload);
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
