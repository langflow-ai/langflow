import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface MemoryInfo {
  id: string;
  name: string;
  description?: string;
  kb_name: string;
  embedding_model: string;
  embedding_provider: string;
  is_active: boolean;
  status: "idle" | "generating" | "updating" | "failed";
  error_message?: string;
  total_messages_processed: number;
  total_chunks: number;
  sessions_count: number;
  batch_size: number;
  preprocessing_enabled: boolean;
  preprocessing_model?: string;
  preprocessing_prompt?: string;
  pending_messages_count: number;
  user_id: string;
  flow_id: string;
  created_at?: string;
  updated_at?: string;
  last_generated_at?: string;
}

interface GetMemoriesParams {
  flowId?: string;
}

export const useGetMemories: useQueryFunctionType<
  GetMemoriesParams,
  MemoryInfo[]
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getMemoriesFn = async (): Promise<MemoryInfo[]> => {
    const url = params?.flowId
      ? `${getURL("MEMORIES")}/?flow_id=${params.flowId}`
      : `${getURL("MEMORIES")}/`;
    const res = await api.get(url);
    return res.data;
  };

  const queryResult: UseQueryResult<MemoryInfo[], any> = query(
    ["useGetMemories", params?.flowId],
    getMemoriesFn,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
