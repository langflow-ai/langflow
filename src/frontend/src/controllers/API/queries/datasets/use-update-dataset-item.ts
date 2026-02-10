import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { DatasetItemInfo } from "./use-get-dataset";

interface UpdateDatasetItemParams {
  datasetId: string;
  itemId: string;
  input?: string;
  expected_output?: string;
  order?: number;
}

export const useUpdateDatasetItem: useMutationFunctionType<
  undefined,
  UpdateDatasetItemParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateDatasetItemFn = async (
    params: UpdateDatasetItemParams,
  ): Promise<DatasetItemInfo> => {
    const response = await api.put<DatasetItemInfo>(
      `${getURL("DATASETS")}/${params.datasetId}/items/${params.itemId}`,
      {
        input: params.input,
        expected_output: params.expected_output,
        order: params.order,
      },
    );
    queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
    queryClient.invalidateQueries({
      queryKey: ["useGetDataset", params.datasetId],
    });
    return response.data;
  };

  const mutation: UseMutationResult<
    DatasetItemInfo,
    any,
    UpdateDatasetItemParams
  > = mutate(["useUpdateDatasetItem"], updateDatasetItemFn, options);

  return mutation;
};
