import { type InfiniteData, keepPreviousData } from "@tanstack/react-query";
import { isAuthenticatedPlayground } from "@/modals/IOModal/helpers/playground-auth";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import {
  isRetryableServerError,
  UseRequestProcessor,
} from "../../services/request-processor";

const SESSIONS_PAGE_SIZE = 100;

interface SessionsPage {
  sessions: string[];
  nextOffset?: number;
}

// Moves the default session (the flow id) to the front, adding it if absent.
function pinDefaultSession(sessionIds: string[], id?: string): string[] {
  if (!id) return sessionIds;
  return [id, ...sessionIds.filter((sessionId) => sessionId !== id)];
}

async function getSessionsPage(
  id: string | undefined,
  offset: number,
): Promise<SessionsPage> {
  const isPlaygroundPage = useFlowStore.getState().playgroundPage;

  // Anonymous/auto-login playground: sessionStorage holds the complete local
  // history, so it is a single page.
  if (isPlaygroundPage && !isAuthenticatedPlayground()) {
    const stored: { session_id?: string | null }[] = JSON.parse(
      window.sessionStorage.getItem(id ?? "") || "[]",
    );
    const sessionIds = new Set(
      stored.flatMap(({ session_id }) => (session_id ? [session_id] : [])),
    );
    return { sessions: pinDefaultSession([...sessionIds], id) };
  }

  // One lookahead row detects the last page without a count or an empty-page click.
  const page = { limit: SESSIONS_PAGE_SIZE + 1, offset };
  const { data } = isPlaygroundPage
    ? await api.get<string[]>(`${getURL("MESSAGES")}/shared/sessions`, {
        params: {
          ...page,
          source_flow_id: useFlowsManagerStore.getState().currentFlowId,
        },
      })
    : await api.get<string[]>(`${getURL("MESSAGES")}/sessions`, {
        params: { ...page, ...(id ? { flow_id: id } : {}) },
      });
  const sessions = data.slice(0, SESSIONS_PAGE_SIZE);

  return {
    // The shared playground lists the virtual default session first.
    sessions:
      isPlaygroundPage && offset === 0
        ? pinDefaultSession(sessions, id)
        : sessions,
    nextOffset:
      data.length > SESSIONS_PAGE_SIZE
        ? offset + SESSIONS_PAGE_SIZE
        : undefined,
  };
}

// A session created while paging shifts later pages by one, so the same id
// can arrive twice; keep its first (most recent) position.
const flattenSessions = (data: InfiniteData<SessionsPage>) => [
  ...new Set(data.pages.flatMap((page) => page.sessions)),
];

/**
 * Session ids of a flow, most recent activity first, one page of
 * `SESSIONS_PAGE_SIZE` at a time (`fetchNextPage` loads older ones). `data` is
 * the de-duplicated list of every loaded page.
 */
export function useGetSessionsFromFlowQuery({
  id,
  enabled = true,
}: {
  id?: string;
  enabled?: boolean;
}) {
  const { infiniteQuery } = UseRequestProcessor();

  return infiniteQuery<SessionsPage, string[]>({
    queryKey: ["useGetSessionsFromFlowQuery", { id }],
    queryFn: ({ pageParam }) => getSessionsPage(id, pageParam),
    initialPageParam: 0,
    getNextPageParam: (page) => page.nextOffset,
    select: flattenSessions,
    placeholderData: keepPreviousData,
    enabled,
    // "Show more" is waited on by the user: one quick retry covers a transient
    // failure, then the error is shown instead of a spinner through the
    // default five retries (~30 s of backoff).
    retry: (failureCount, error) =>
      failureCount < 1 && isRetryableServerError(error),
    // Invalidation refetches every loaded page, so a focus refetch would cost
    // one request per page. Sends, renames and deletes in this tab already
    // invalidate the list; changes from other tabs show up on the next one.
    refetchOnWindowFocus: false,
  });
}
