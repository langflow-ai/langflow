import type { UseMutationResult } from "@tanstack/react-query";
import { BASE_URL_API } from "@/constants/constants";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "@/controllers/API/api";
import { UseRequestProcessor } from "../../services/request-processor";

interface IDeleteFlowFile {
  flowId: string;
  fileName: string;
}

export const useDeleteFlowFile: useMutationFunctionType<
  undefined,
  IDeleteFlowFile
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteFlowFileFn = async (params: IDeleteFlowFile): Promise<any> => {
    const response = await api.delete<any>(
      `${BASE_URL_API}files/delete/${params.flowId}/${params.fileName}`,
    );
    return response.data;
  };

  const mutation: UseMutationResult<any, any, IDeleteFlowFile> = mutate(
    ["useDeleteFlowFile"],
    deleteFlowFileFn,
    {
      ...options,
      onSettled: (...args) => {
        queryClient.invalidateQueries({
          queryKey: ["useGetFlowFiles"],
        });
        options?.onSettled?.(...args);
      },
    },
  );

  return mutation;
};
