import { useEffect, useRef } from "react";
import { isAuthenticatedPlayground } from "@/modals/IOModal/helpers/playground-auth";
import useFlowStore from "@/stores/flowStore";
import { useMessagesStore } from "@/stores/messagesStore";
import type { Message } from "@/types/messages";
import { UseRequestProcessor } from "../../services/request-processor";
import { getMessages, UnknownMessageCursorError } from "./use-get-messages";

const PAGE_SIZE = 100;
// Anchors tried against the server when rows were deleted elsewhere.
const MAX_CURSOR_ATTEMPTS = 3;

interface HistoryPage {
  messages: Message[];
  hasMore: boolean;
}

// Every fetched row id, oldest first: the candidates for the next cursor.
type FetchedIds = string[];

/**
 * Pick the cursor for the next page: the oldest fetched row that has not been
 * deleted. Any row between it and a deleted anchor is gone too, so it yields
 * exactly the page the deleted anchor would have.
 */
const cursorCandidates = (fetchedIds: FetchedIds, id?: string): string[] => {
  const present = new Set(
    useMessagesStore
      .getState()
      .messages.filter((message) => !id || message.flow_id === id)
      .map((message) => message.id),
  );
  return fetchedIds
    .filter((messageId) => present.has(messageId))
    .slice(0, MAX_CURSOR_ATTEMPTS);
};

export function useGetMessageHistory({
  id,
  sessionId,
  enabled = true,
}: {
  id?: string;
  sessionId?: string;
  enabled?: boolean;
}) {
  const { infiniteQuery } = UseRequestProcessor();
  const playground = useFlowStore.getState().playgroundPage;
  const shared = isAuthenticatedPlayground();
  const scope = JSON.stringify([id, sessionId, playground, shared]);
  const applied = useRef<{ scope: string; pages: HistoryPage[] } | undefined>(
    undefined,
  );
  const history = infiniteQuery<HistoryPage, FetchedIds | null>({
    // A distinct suffix avoids sharing the ordinary message query's response shape.
    queryKey: [
      "useGetMessagesQuery",
      { id, session_id: sessionId, playground, shared },
      "history",
    ],
    initialPageParam: null,
    queryFn: async ({ pageParam }) => {
      if (playground && !shared) {
        // The anonymous playground persists this store as its complete local
        // history. Keep all sessions so saving it cannot discard unloaded rows.
        const { data } = await getMessages(id, { order: "DESC" });
        return { messages: data, hasMore: false };
      }
      const params = {
        ...(sessionId ? { session_id: sessionId } : {}),
        // One lookahead row detects the last page without a count or an empty-page click.
        limit: PAGE_SIZE + 1,
        order: "DESC",
      };
      // A cursor rather than an offset: messages that arrive or are deleted
      // while older pages load would otherwise shift every offset window.
      // With every fetched row deleted, the newest page is the continuation.
      const candidates = pageParam ? cursorCandidates(pageParam, id) : [];
      let data: Message[] | undefined;
      for (let attempt = 0; data === undefined; attempt++) {
        const beforeId = candidates[attempt];
        try {
          ({ data } = await getMessages(id, {
            ...params,
            ...(beforeId ? { before_id: beforeId } : {}),
          }));
        } catch (error) {
          if (!(error instanceof UnknownMessageCursorError)) throw error;
          if (attempt >= candidates.length - 1) throw error.original ?? error;
        }
      }
      return {
        messages: data.slice(0, PAGE_SIZE),
        hasMore: data.length > PAGE_SIZE,
      };
    },
    getNextPageParam: (page, pages) =>
      page.hasMore
        ? pages
            .flatMap((fetched) => fetched.messages)
            .reverse()
            .flatMap((message) => (message.id ? [message.id] : []))
        : undefined,
    enabled,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (!enabled || !history.data) return;
    const pages = history.data.pages;
    const previous = applied.current;
    const appending =
      previous?.scope === scope &&
      pages.length > previous.pages.length &&
      previous.pages.every((page, index) => page === pages[index]);
    const store = useMessagesStore.getState();
    const otherFlows = id ? store.messages.filter((m) => m.flow_id !== id) : [];
    const current = id
      ? store.messages.filter((m) => m.flow_id === id)
      : store.messages;
    // Loading older rows must not overwrite live messages, edits, or deletions
    // made since the first page was fetched. Only merge the newly fetched pages.
    const incoming = (appending ? pages.slice(previous.pages.length) : pages)
      .flatMap((page) => page.messages)
      .reverse();
    const seen = new Set(appending ? current.map((message) => message.id) : []);
    const unique = incoming.filter((message) => {
      if (message.id && seen.has(message.id)) return false;
      seen.add(message.id);
      return true;
    });
    store.setMessages([
      ...otherFlows,
      ...unique,
      ...(appending ? current : []),
    ]);
    applied.current = { scope, pages };
  }, [history.data, enabled, id, scope]);

  return history;
}
