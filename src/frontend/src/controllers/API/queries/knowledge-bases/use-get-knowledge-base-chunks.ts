import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ChunkInfo {
  id: string;
  content: string;
  char_count: number;
  metadata: Record<string, unknown> | null;
}

export interface PaginatedChunkResponse {
  chunks: ChunkInfo[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

interface GetKnowledgeBaseChunksParams {
  kb_name: string;
  page?: number;
  limit?: number;
  search?: string;
  source_type?: string;
  file_name?: string;
  job_id?: string;
}

export const useGetKnowledgeBaseChunks: useQueryFunctionType<
  GetKnowledgeBaseChunksParams,
  PaginatedChunkResponse
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getChunksFn = async (): Promise<PaginatedChunkResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.page) {
      queryParams.append("page", params.page.toString());
    }
    if (params?.limit) {
      queryParams.append("limit", params.limit.toString());
    }
    if (params?.search) {
      queryParams.append("search", params.search);
    }
    if (params?.source_type) {
      queryParams.append("source_type", params.source_type);
    }
    if (params?.file_name) {
      queryParams.append("file_name", params.file_name);
    }
    if (params?.job_id) {
      queryParams.append("job_id", params.job_id);
    }

    const url = `${getURL("KNOWLEDGE_BASES")}/${params?.kb_name}/chunks${
      queryParams.toString() ? `?${queryParams.toString()}` : ""
    }`;

    const res = await api.get(url);
    return res.data;
  };

  const queryResult: UseQueryResult<PaginatedChunkResponse, Error> = query(
    [
      "useGetKnowledgeBaseChunks",
      params?.kb_name,
      params?.page,
      params?.limit,
      params?.search,
      params?.source_type,
      params?.file_name,
      params?.job_id,
    ],
    getChunksFn,
    {
      enabled: !!params?.kb_name,
      retry: (failureCount, error: unknown) => {
        const status = (error as { response?: { status?: unknown } })?.response
          ?.status;
        if (typeof status === "number") {
          return status >= 500 && failureCount < 3;
        }
        return failureCount < 3;
      },
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
