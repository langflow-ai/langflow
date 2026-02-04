import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DatasetItemInfo {
  id: string;
  dataset_id: string;
  input: string;
  expected_output: string;
  order: number;
  created_at: string;
}

export interface DatasetWithItems {
  id: string;
  name: string;
  description?: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  item_count: number;
  items: DatasetItemInfo[];
}

interface GetDatasetParams {
  datasetId: string;
}

export const useGetDataset: useQueryFunctionType<
  GetDatasetParams,
  DatasetWithItems
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getDatasetFn = async (): Promise<DatasetWithItems> => {
    const res = await api.get(`${getURL("DATASETS")}/${params.datasetId}`);
    return res.data;
  };

  const queryResult: UseQueryResult<DatasetWithItems, any> = query(
    ["useGetDataset", params.datasetId],
    getDatasetFn,
    {
      refetchOnWindowFocus: false,
      enabled: !!params.datasetId,
      ...options,
    },
  );

  return queryResult;
};
