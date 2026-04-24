import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ConnectorIngestRequest {
  kb_name: string;
  source_type: string;
  source_config: Record<string, unknown>;
  source_name?: string;
  chunk_size?: number;
  chunk_overlap?: number;
  separator?: string;
}

export interface ConnectorIngestResponse {
  id: string;
  href: string;
}

export const useIngestViaConnector: useMutationFunctionType<
  undefined,
  ConnectorIngestRequest,
  ConnectorIngestResponse
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const ingestFn = async (
    payload: ConnectorIngestRequest,
  ): Promise<ConnectorIngestResponse> => {
    const { kb_name, ...body } = payload;
    const url = `${getURL("KNOWLEDGE_BASES")}/${kb_name}/ingest/connector`;
    const res = await api.post<ConnectorIngestResponse>(url, {
      source_type: body.source_type,
      source_config: body.source_config,
      source_name: body.source_name ?? "",
      chunk_size: body.chunk_size ?? 1000,
      chunk_overlap: body.chunk_overlap ?? 200,
      separator: body.separator ?? "",
    });
    return res.data;
  };

  // Cache invalidation is the caller's responsibility — the mutate
  // wrapper's ``onSuccess`` signature doesn't type the variables
  // parameter correctly, so callers pass an ``onSuccess`` into
  // ``options`` instead and invalidate from there.
  const mutation: UseMutationResult<
    ConnectorIngestResponse,
    Error,
    ConnectorIngestRequest
  > = mutate(["useIngestViaConnector"], ingestFn, {
    ...options,
  });

  return mutation;
};
