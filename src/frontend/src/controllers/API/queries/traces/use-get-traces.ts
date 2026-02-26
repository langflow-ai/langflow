import { keepPreviousData } from "@tanstack/react-query";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { sanitizeParams, sanitizeString } from "./helpers";
import type { TracesQueryParams, TracesResponse } from "./types";

export const useGetTracesQuery: useQueryFunctionType<
  TracesQueryParams,
  TracesResponse
> = ({ flowId, sessionId, params }, options) => {
  const { query } = UseRequestProcessor();

  const getTracesFn = async (): Promise<TracesResponse> => {
    if (!flowId) return { traces: [], total: 0 };

    const config: { params: Record<string, unknown> } = {
      params: { flow_id: sanitizeString(flowId) },
    };

    if (sessionId) {
      config.params.session_id = sanitizeString(sessionId);
    }

    if (params) {
      config.params = sanitizeParams({ ...config.params, ...params });
    }

    const result = await api.get<TracesResponse>(`${getURL("TRACES")}`, config);

    return result.data;
  };

  const queryResult = query(
    ["useGetTracesQuery", flowId, sessionId, { ...params }],
    getTracesFn,
    {
      placeholderData: keepPreviousData,
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
