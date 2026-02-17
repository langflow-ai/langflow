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

interface GetKnowledgeBaseChunksParams {
  kb_name: string;
}

export const useGetKnowledgeBaseChunks: useQueryFunctionType<
  GetKnowledgeBaseChunksParams,
  ChunkInfo[]
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getChunksFn = async (): Promise<ChunkInfo[]> => {
    const res = await api.get(
      `${getURL("KNOWLEDGE_BASES")}/${params?.kb_name}/chunks`,
    );
    return res.data;
  };

  const queryResult: UseQueryResult<ChunkInfo[], any> = query(
    ["useGetKnowledgeBaseChunks", params?.kb_name],
    getChunksFn,
    {
      enabled: !!params?.kb_name,
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
