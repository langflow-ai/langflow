import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface KbMetadataKeysResponse {
  /**
   * Map of distinct user-supplied metadata keys to a sample of their
   * stringified distinct values. Reserved ingestion-internal keys
   * (`file_name`, `source`, etc.) are excluded server-side.
   */
  keys: Record<string, string[]>;
  /**
   * True when at least one key's distinct-value list hit the server-side
   * cap. UI uses this to surface a "showing first N values" hint.
   */
  truncated: boolean;
}

interface GetKbMetadataKeysParams {
  kb_name: string;
}

export const useGetKbMetadataKeys: useQueryFunctionType<
  GetKbMetadataKeysParams,
  KbMetadataKeysResponse
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getKeysFn = async (): Promise<KbMetadataKeysResponse> => {
    const url = `${getURL("KNOWLEDGE_BASES")}/${params?.kb_name}/metadata/keys`;
    const res = await api.get<KbMetadataKeysResponse>(url);
    return res.data;
  };

  const queryResult: UseQueryResult<KbMetadataKeysResponse, Error> = query(
    ["useGetKbMetadataKeys", params?.kb_name],
    getKeysFn,
    {
      enabled: !!params?.kb_name,
      // Always refetch on mount / when the popover re-enables this hook so
      // metadata added by a fresh ingestion shows up in the dropdown without
      // a hard refresh. The endpoint scans chunks server-side so a per-open
      // refetch is the safest invalidation path — cheaper than wiring an
      // ingestion-completion event into this hook from another component.
      staleTime: 0,
      refetchOnMount: "always",
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
