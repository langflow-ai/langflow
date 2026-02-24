import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { DatasetInfo } from "./use-get-datasets";

interface CreateDatasetParams {
  name: string;
  description?: string;
}

export const useCreateDataset: useMutationFunctionType<
  undefined,
  CreateDatasetParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createDatasetFn = async (
    params: CreateDatasetParams,
  ): Promise<DatasetInfo> => {
    const response = await api.post<DatasetInfo>(`${getURL("DATASETS")}/`, {
      name: params.name,
      description: params.description,
    });
    queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
    return response.data;
  };

  const mutation: UseMutationResult<DatasetInfo, any, CreateDatasetParams> =
    mutate(["useCreateDataset"], createDatasetFn, options);

  return mutation;
};
