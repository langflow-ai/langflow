import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteDatasetItemParams {
  datasetId: string;
  itemId: string;
}

export const useDeleteDatasetItem: useMutationFunctionType<
  DeleteDatasetItemParams,
  void
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteDatasetItemFn = async (): Promise<void> => {
    await api.delete(
      `${getURL("DATASETS")}/${params.datasetId}/items/${params.itemId}`,
    );
    queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
    queryClient.invalidateQueries({
      queryKey: ["useGetDataset", params.datasetId],
    });
  };

  const mutation: UseMutationResult<void, any, void> = mutate(
    ["useDeleteDatasetItem"],
    deleteDatasetItemFn,
    options,
  );

  return mutation;
};
