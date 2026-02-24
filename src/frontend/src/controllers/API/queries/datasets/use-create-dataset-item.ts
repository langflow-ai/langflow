import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { DatasetItemInfo } from "./use-get-dataset";

interface CreateDatasetItemParams {
  datasetId: string;
  input: string;
  expected_output: string;
  order?: number;
}

export const useCreateDatasetItem: useMutationFunctionType<
  undefined,
  CreateDatasetItemParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createDatasetItemFn = async (
    params: CreateDatasetItemParams,
  ): Promise<DatasetItemInfo> => {
    const response = await api.post<DatasetItemInfo>(
      `${getURL("DATASETS")}/${params.datasetId}/items`,
      {
        input: params.input,
        expected_output: params.expected_output,
        order: params.order ?? 0,
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
    CreateDatasetItemParams
  > = mutate(["useCreateDatasetItem"], createDatasetItemFn, options);

  return mutation;
};
