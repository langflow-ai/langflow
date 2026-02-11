import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface MemoryDocumentItem {
  content: string;
  sender: string;
  session_id: string;
  timestamp: string;
  message_id: string;
}

export interface MemoryDocumentsResponse {
  documents: MemoryDocumentItem[];
  total: number;
  sessions: string[];
}

interface GetMemoryDocumentsParams {
  memoryId?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export const useGetMemoryDocuments: useQueryFunctionType<
  GetMemoryDocumentsParams,
  MemoryDocumentsResponse
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getDocumentsFn = async (): Promise<MemoryDocumentsResponse> => {
    if (!params?.memoryId) {
      return { documents: [], total: 0, sessions: [] };
    }
    const searchParams = new URLSearchParams();
    if (params.search) searchParams.set("search", params.search);
    if (params.limit) searchParams.set("limit", String(params.limit));
    if (params.offset) searchParams.set("offset", String(params.offset));
    const qs = searchParams.toString();
    const url = `${getURL("MEMORIES")}/${params.memoryId}/documents${qs ? `?${qs}` : ""}`;
    const res = await api.get<MemoryDocumentsResponse>(url);
    return res.data;
  };

  const queryResult: UseQueryResult<MemoryDocumentsResponse, any> = query(
    ["useGetMemoryDocuments", params?.memoryId, params?.search, params?.limit, params?.offset],
    getDocumentsFn,
    {
      refetchOnWindowFocus: false,
      enabled: !!params?.memoryId,
      ...options,
    },
  );

  return queryResult;
};
