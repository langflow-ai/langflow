import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { DatasetInfo } from "./use-get-datasets";

export interface GenerateStatusResponse {
  status: "completed" | "failed" | "unknown";
  item_count?: number;
  error?: string;
  token_usage?: {
    input_tokens?: number;
    output_tokens?: number;
    total_tokens?: number;
  };
}

export async function fetchGenerateStatus(
  datasetId: string,
  { consume = true }: { consume?: boolean } = {},
): Promise<GenerateStatusResponse> {
  const response = await api.get<GenerateStatusResponse>(
    `${getURL("DATASETS")}/generate-status/${datasetId}`,
    { params: { consume } },
  );
  return response.data;
}

interface GenerateDatasetParams {
  name: string;
  description?: string;
  topic: string;
  num_items: number;
  model: Record<string, any>;
}

export const useGenerateDataset: useMutationFunctionType<
  undefined,
  GenerateDatasetParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const generateDatasetFn = async (
    params: GenerateDatasetParams,
  ): Promise<DatasetInfo> => {
    const response = await api.post<DatasetInfo>(
      `${getURL("DATASETS")}/generate`,
      {
        name: params.name,
        description: params.description,
        topic: params.topic,
        num_items: params.num_items,
        model: params.model,
      },
    );
    queryClient.invalidateQueries({ queryKey: ["useGetDatasets"] });
    return response.data;
  };

  const mutation: UseMutationResult<
    DatasetInfo,
    any,
    GenerateDatasetParams
  > = mutate(["useGenerateDataset"], generateDatasetFn, options);

  return mutation;
};
