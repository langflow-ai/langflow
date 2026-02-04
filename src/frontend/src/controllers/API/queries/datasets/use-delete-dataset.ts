import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteDatasetParams {
  datasetId: string;
}

export const useDeleteDataset: useMutationFunctionType<
  DeleteDatasetParams,
  void
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteDatasetFn = async (): Promise<void> => {
    await api.delete(`${getURL("DATASETS")}/${params.datasetId}`);
    queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
  };

  const mutation: UseMutationResult<void, any, void> = mutate(
    ["useDeleteDataset"],
    deleteDatasetFn,
    options,
  );

  return mutation;
};
