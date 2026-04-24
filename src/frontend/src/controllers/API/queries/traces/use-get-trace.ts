import type { Trace } from "../../../../pages/FlowPage/components/TraceComponent/types";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { convertTrace } from "./helpers";
import { TraceApiResponse, TraceQueryParams } from "./types";

export const useGetTraceQuery: useQueryFunctionType<
  TraceQueryParams,
  Trace | null
> = ({ traceId }, options) => {
  const { query } = UseRequestProcessor();

  const getTraceFn = async (): Promise<Trace | null> => {
    if (!traceId) return null;

    const result = await api.get<TraceApiResponse>(
      `${getURL("TRACES")}/${encodeURIComponent(traceId)}`,
    );

    return convertTrace(result.data);
  };

  const queryResult = query(["useGetTraceQuery", traceId], getTraceFn, {
    refetchOnWindowFocus: false,
    enabled: !!traceId,
    ...options,
  });

  return queryResult;
};
