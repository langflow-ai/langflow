import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { DatasetInfo } from "./use-get-datasets";

interface UpdateDatasetParams {
  datasetId: string;
  name?: string;
  description?: string;
}

export const useUpdateDataset: useMutationFunctionType<
  undefined,
  UpdateDatasetParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateDatasetFn = async (
    params: UpdateDatasetParams,
  ): Promise<DatasetInfo> => {
    const response = await api.put<DatasetInfo>(
      `${getURL("DATASETS")}/${params.datasetId}`,
      {
        name: params.name,
        description: params.description,
      },
    );
    queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
    queryClient.invalidateQueries({
      queryKey: ["useGetDataset", params.datasetId],
    });
    return response.data;
  };

  const mutation: UseMutationResult<DatasetInfo, any, UpdateDatasetParams> =
    mutate(["useUpdateDataset"], updateDatasetFn, options);

  return mutation;
};
