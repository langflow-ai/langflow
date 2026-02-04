import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DatasetInfo {
  id: string;
  name: string;
  description?: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  item_count: number;
}

export const useGetDatasets: useQueryFunctionType<undefined, DatasetInfo[]> = (
  options?,
) => {
  const { query } = UseRequestProcessor();

  const getDatasetsFn = async (): Promise<DatasetInfo[]> => {
    const res = await api.get(`${getURL("DATASETS")}/`);
    return res.data;
  };

  const queryResult: UseQueryResult<DatasetInfo[], any> = query(
    ["useGetDatasets"],
    getDatasetsFn,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
