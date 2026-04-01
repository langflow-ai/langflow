import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface KnowledgeBaseInfo {
  id: string;
  dir_name: string;
  name: string;
  embedding_provider?: string;
  embedding_model?: string;
  size: number;
  words: number;
  characters: number;
  chunks: number;
  avg_chunk_size: number;
  chunk_size?: number;
  chunk_overlap?: number;
  separator?: string;
  status?: string;
  failure_reason?: string | null;
  source_types?: string[];
  column_config?: Array<{
    column_name: string;
    vectorize: boolean;
    identifier: boolean;
  }>;
}

export const useGetKnowledgeBases: useQueryFunctionType<
  undefined,
  KnowledgeBaseInfo[]
> = (options?) => {
  const { query } = UseRequestProcessor();

  const getKnowledgeBasesFn = async (): Promise<KnowledgeBaseInfo[]> => {
    const res = await api.get(`${getURL("KNOWLEDGE_BASES")}/`);
    return res.data;
  };

  const queryResult: UseQueryResult<KnowledgeBaseInfo[], any> = query(
    ["useGetKnowledgeBases"],
    getKnowledgeBasesFn,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
