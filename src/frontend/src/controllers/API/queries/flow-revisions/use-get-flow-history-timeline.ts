import { keepPreviousData, type UseQueryResult } from "@tanstack/react-query";
import type { RevisionEntry } from "@/types/flow/revision";
import type { FlowGraph } from "@/utils/flow-operations/apply";
import {
  buildHistoryTimeline,
  type HistoryTimeline,
} from "@/utils/flow-operations/history";
import { UseRequestProcessor } from "../../services/request-processor";
import { getFlowRevision } from "./use-get-flow-revision";
import { getFlowRevisions, MAX_PAGE_SIZE } from "./use-get-flow-revisions";

/**
 * Load every retained entry with its operations, and the graph to replay
 * them from: the revision before the oldest entry, or, when compaction cut
 * there, the oldest entry's end, which always has a checkpoint.
 */
export const getFlowHistoryTimeline = async (
  flowId: string,
): Promise<HistoryTimeline | null> => {
  const newestFirst: RevisionEntry[] = [];
  let before = 0;
  do {
    const page = await getFlowRevisions(flowId, before, MAX_PAGE_SIZE);
    newestFirst.push(...page.entries);
    before = page.next_before ?? 0;
  } while (before > 0);
  if (newestFirst.length === 0) return null;

  const entries = newestFirst.reverse();
  const oldest = entries[0];
  let baseRevision = oldest.start_revision - 1;
  let base: FlowGraph;
  try {
    base = (await getFlowRevision(flowId, baseRevision)).data as FlowGraph;
  } catch {
    baseRevision = oldest.end_revision;
    base = (await getFlowRevision(flowId, baseRevision)).data as FlowGraph;
  }
  return buildHistoryTimeline({ flowId, baseRevision, base, entries });
};

/**
 * The flow's whole retained history, replayed for the history slider.
 *
 * Keyed on the latest revision: recorded history never changes, so it is
 * loaded again only when something new has been recorded.
 */
export const useGetFlowHistoryTimeline = (
  flowId: string,
  latestRevision: number | null,
) => {
  const { query } = UseRequestProcessor();

  return query(
    ["useGetFlowHistoryTimeline", { flowId, latestRevision }],
    () => getFlowHistoryTimeline(flowId),
    {
      enabled: !!flowId && !!latestRevision,
      staleTime: Number.POSITIVE_INFINITY,
      retry: false,
      placeholderData: keepPreviousData,
    },
  ) as UseQueryResult<HistoryTimeline | null>;
};
