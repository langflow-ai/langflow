import type { UseQueryResult } from "@tanstack/react-query";
import { useEffect } from "react";
import type { RevisionPage } from "@/types/flow/revision";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

const PAGE_SIZE = 50;
/** The largest page the server returns. */
export const MAX_PAGE_SIZE = 200;
// Revisions start at 1, so 0 stands for "from the newest entry".
const NEWEST = 0;

export const getFlowRevisions = async (
  flowId: string,
  before: number = NEWEST,
  limit: number = PAGE_SIZE,
  withOperations = true,
): Promise<RevisionPage> => {
  const response = await api.get<RevisionPage>(
    `${getURL("FLOWS")}/${flowId}/revisions`,
    {
      params: {
        limit,
        ...(withOperations ? { include: "operations" } : {}),
        ...(before > NEWEST ? { before } : {}),
      },
    },
  );
  return response.data;
};

/** Whether the history changed since `loaded`: new revisions, or compaction. */
export const historyChanged = (
  loaded: RevisionPage,
  newest: RevisionPage,
): boolean =>
  newest.latest_revision !== loaded.latest_revision ||
  newest.current_revision !== loaded.current_revision ||
  newest.earliest_revision !== loaded.earliest_revision;

/**
 * The flow's timeline, newest first, loaded a page at a time.
 *
 * With `pollInterval`, only the newest entry is asked for at that interval,
 * without its operations. The loaded pages are reloaded only when that
 * shows the history changed.
 */
export const useGetFlowRevisions = (
  flowId: string,
  options?: { enabled?: boolean; pollInterval?: number },
) => {
  const { infiniteQuery, query } = UseRequestProcessor();
  const enabled = !!flowId && (options?.enabled ?? true);

  const revisions = infiniteQuery<RevisionPage>({
    queryKey: ["useGetFlowRevisions", { flowId }],
    queryFn: ({ pageParam }) => getFlowRevisions(flowId, pageParam),
    initialPageParam: NEWEST,
    getNextPageParam: (lastPage) => lastPage.next_before ?? undefined,
    enabled,
  });

  const { data: newest, dataUpdatedAt: newestUpdatedAt } = query(
    ["useGetFlowRevisionsNewest", { flowId }],
    () => getFlowRevisions(flowId, NEWEST, 1, false),
    {
      enabled: enabled && !!options?.pollInterval,
      refetchInterval: options?.pollInterval,
    },
  ) as UseQueryResult<RevisionPage>;

  const loaded = revisions.data?.pages[0];
  const { dataUpdatedAt, errorUpdatedAt, isFetching, refetch } = revisions;
  useEffect(() => {
    if (!newest || !loaded || isFetching) return;
    // Only a poll newer than the last load, or the last failed one, can say
    // the pages are out of date.
    if (newestUpdatedAt <= Math.max(dataUpdatedAt, errorUpdatedAt)) return;
    if (historyChanged(loaded, newest)) refetch();
  }, [
    newest,
    newestUpdatedAt,
    loaded,
    dataUpdatedAt,
    errorUpdatedAt,
    isFetching,
    refetch,
  ]);

  return revisions;
};
