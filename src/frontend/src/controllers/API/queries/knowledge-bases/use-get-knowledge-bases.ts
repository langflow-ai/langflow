import { UseQueryResult } from "@tanstack/react-query";
import { ENABLE_KNOWLEDGE_BASES } from "@/customization/feature-flags";
import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface KnowledgeBaseInfo {
  id: string;
  name: string;
  embedding_provider?: string;
  embedding_model?: string;
  size: number;
  words: number;
  characters: number;
  chunks: number;
  avg_chunk_size: number;
}

export const useGetKnowledgeBases: useQueryFunctionType<
  undefined,
  KnowledgeBaseInfo[]
> = (options?) => {
  const { query } = UseRequestProcessor();

  const getKnowledgeBasesFn = async (): Promise<KnowledgeBaseInfo[]> => {
    if (!ENABLE_KNOWLEDGE_BASES) {
      return [];
    }
    const res = await api.get(`${getURL("KNOWLEDGE_BASES")}/`);
    return res.data;
  };

  const queryResult: UseQueryResult<KnowledgeBaseInfo[], any> = query(
    ["useGetKnowledgeBases"],
    getKnowledgeBasesFn,
    {
      refetchOnWindowFocus: false,
      enabled: ENABLE_KNOWLEDGE_BASES,
      ...options,
    },
  );

  return queryResult;
};
