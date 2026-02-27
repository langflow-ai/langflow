import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface IngestionJobStatusResponse {
  job_id: string;
  status: string;
  created_at: string | null;
  finished_at: string | null;
}

interface GetIngestionJobStatusParams {
  job_id: string | null;
}

export const useGetIngestionJobStatus: useQueryFunctionType<
  GetIngestionJobStatusParams,
  IngestionJobStatusResponse
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getStatusFn = async (): Promise<IngestionJobStatusResponse> => {
    const url = `${getURL("KNOWLEDGE_BASES")}/jobs/${params?.job_id}`;
    const res = await api.get(url);
    return res.data;
  };

  const queryResult: UseQueryResult<IngestionJobStatusResponse, any> = query(
    ["useGetIngestionJobStatus", params?.job_id],
    getStatusFn,
    {
      enabled: !!params?.job_id,
      refetchInterval: (query) => {
        const data = query.state.data;
        if (
          data?.status === "completed" ||
          data?.status === "failed" ||
          data?.status === "cancelled"
        ) {
          return false;
        }
        return 6000;
      },
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
