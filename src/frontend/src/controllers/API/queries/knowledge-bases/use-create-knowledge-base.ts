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
  /**
   * Exact unified-model selection captured at create time. Retrieval uses
   * this instead of resolving by provider/name again, which avoids drift
   * when multiple providers expose the same model name.
   */
  model_selection?: unknown;
  column_config?: Array<{
    column_name: string;
    vectorize: boolean;
    identifier: boolean;
  }>;
  /**
   * Vector-store backend selector. Defaults to "chroma" on the server
   * when omitted so existing callers keep working unchanged. In this
   * phase only "chroma" and "opensearch" are accepted; the server
   * rejects other values.
   */
  backend_type?: string;
  /**
   * Per-backend configuration. Shape depends on ``backend_type``:
   *
   * - ``"chroma"``: ``{}`` (no config — uses the on-disk KB directory)
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
  const { mutate } = UseRequestProcessor();

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
