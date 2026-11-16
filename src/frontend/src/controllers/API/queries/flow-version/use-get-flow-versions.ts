import type { useQueryFunctionType } from "@/types/api";
import type { FlowVersionListResponse } from "@/types/flow/version";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface FlowVersionParams {
  flowId: string;
  limit?: number;
  offset?: number;
  /** Every entry, page by page: versions kept by evaluation runs can push a flow past `max_entries`. */
  all?: boolean;
}

// The largest page the list endpoint serves.
const MAX_PAGE = 100;

export const useGetFlowVersions: useQueryFunctionType<
  FlowVersionParams,
  FlowVersionListResponse
> = ({ flowId, limit = 50, offset = 0, all = false }, options) => {
  const { query } = UseRequestProcessor();

  const fetchPage = async (pageLimit: number, pageOffset: number) =>
    (
      await api.get<FlowVersionListResponse>(
        `${getURL("FLOWS")}/${flowId}/versions/`,
        { params: { limit: pageLimit, offset: pageOffset } },
      )
    ).data;

  const getFlowVersionsFn = async (): Promise<FlowVersionListResponse> => {
    if (!all) return fetchPage(limit, offset);
    const first = await fetchPage(MAX_PAGE, 0);
    const entries = [...first.entries];
    let page = first.entries;
    while (page.length === MAX_PAGE) {
      page = (await fetchPage(MAX_PAGE, entries.length)).entries;
      entries.push(...page);
    }
    return { ...first, entries };
  };

  return query(
    ["useGetFlowVersions", { flowId, limit, offset, all }],
    getFlowVersionsFn,
    options,
  );
};
