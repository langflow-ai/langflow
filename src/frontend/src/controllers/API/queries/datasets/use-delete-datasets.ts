import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteDatasetsParams {
  dataset_ids: string[];
}

export const useDeleteDatasets: useMutationFunctionType<
  undefined,
  DeleteDatasetsParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteDatasetsFn = async (
    params: DeleteDatasetsParams,
  ): Promise<{ deleted: number }> => {
    const response = await api.delete<{ deleted: number }>(
      `${getURL("DATASETS")}/`,
      {
        data: { dataset_ids: params.dataset_ids },
      },
    );
    queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
    return response.data;
  };

  const mutation: UseMutationResult<
    { deleted: number },
    any,
    DeleteDatasetsParams
  > = mutate(["useDeleteDatasets"], deleteDatasetsFn, options);

  return mutation;
};
