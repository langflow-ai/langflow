import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface IngestionRunInfo {
  id: string;
  kb_name: string;
  kb_id: string | null;
  job_id: string | null;
  source_type: string;
  source_name: string | null;
  status: string;
  error_message: string | null;
  total_items: number;
  succeeded: number;
  failed: number;
  skipped: number;
  total_bytes: number;
  chunks_created: number;
  started_at: string;
  finished_at: string | null;
}

export interface PaginatedIngestionRunResponse {
  runs: IngestionRunInfo[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

interface GetIngestionRunsParams {
  kb_name: string;
  page?: number;
  limit?: number;
}

export const useGetIngestionRuns: useQueryFunctionType<
  GetIngestionRunsParams,
  PaginatedIngestionRunResponse
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getRunsFn = async (): Promise<PaginatedIngestionRunResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.page) {
      queryParams.append("page", params.page.toString());
    }
    if (params?.limit) {
      queryParams.append("limit", params.limit.toString());
    }

    const url = `${getURL("KNOWLEDGE_BASES")}/${params?.kb_name}/runs${
      queryParams.toString() ? `?${queryParams.toString()}` : ""
    }`;

    const res = await api.get<PaginatedIngestionRunResponse>(url);
    return res.data;
  };

  const queryResult: UseQueryResult<PaginatedIngestionRunResponse, Error> =
    query(
      ["useGetIngestionRuns", params?.kb_name, params?.page, params?.limit],
      getRunsFn,
      {
        enabled: !!params?.kb_name,
        refetchOnWindowFocus: false,
        ...options,
      },
    );

  return queryResult;
};
