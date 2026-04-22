import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { KnowledgeBaseInfo } from "./use-get-knowledge-bases";

export interface CreateKnowledgeBaseRequest {
  name: string;
  embedding_provider: string;
  embedding_model: string;
  column_config?: Array<{
    column_name: string;
    vectorize: boolean;
    identifier: boolean;
  }>;
  /**
   * Phase 4: vector-store backend selector. Defaults to "chroma" on
   * the server when omitted so existing callers keep working unchanged.
   */
  backend_type?: string;
  /**
   * Per-backend configuration. Shape depends on ``backend_type``:
   *
   * - ``"chroma"``: ``{}`` (no config — uses the on-disk KB directory)
   * - ``"mongodb"``: ``{ connection_uri_variable, database, collection,
   *   index_name?, text_key?, embedding_key? }``
   * - ``"astra"``: ``{ api_endpoint_variable?, token_variable?,
   *   collection_name, namespace? }``
   * - ``"postgres"``: ``{ connection_uri_variable?, collection_name }``
   * - ``"opensearch"``: ``{ url_variable?, username_variable?,
   *   password_variable?, index_name, vector_field?, text_field? }``
   *
   * Credentials are referenced by Langflow-variable *name*, never
   * embedded as raw secrets.
   */
  backend_config?: Record<string, unknown>;
}

export const useCreateKnowledgeBase: useMutationFunctionType<
  undefined,
  CreateKnowledgeBaseRequest,
  KnowledgeBaseInfo
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createKnowledgeBaseFn = async (
    payload: CreateKnowledgeBaseRequest,
  ): Promise<KnowledgeBaseInfo> => {
    const res = await api.post<KnowledgeBaseInfo>(
      `${getURL("KNOWLEDGE_BASES")}/`,
      payload,
    );
    return res.data;
  };

  const mutation: UseMutationResult<
    KnowledgeBaseInfo,
    Error,
    CreateKnowledgeBaseRequest
  > = mutate(["useCreateKnowledgeBase"], createKnowledgeBaseFn, {
    ...options,
  });

  return mutation;
};
