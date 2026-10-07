import { useEffect, useRef } from "react";
import { isAuthenticatedPlayground } from "@/modals/IOModal/helpers/playground-auth";
import useFlowStore from "@/stores/flowStore";
import { useMessagesStore } from "@/stores/messagesStore";
import type { Message } from "@/types/messages";
import { UseRequestProcessor } from "../../services/request-processor";
import { getMessages } from "./use-get-messages";

const PAGE_SIZE = 100;

interface HistoryPage {
  messages: Message[];
  nextOffset?: number;
}

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
  const history = infiniteQuery<HistoryPage>({
    // A distinct suffix avoids sharing the ordinary message query's response shape.
    queryKey: [
      "useGetMessagesQuery",
      { id, session_id: sessionId, playground, shared },
      "history",
    ],
    initialPageParam: 0,
    queryFn: async ({ pageParam }) => {
      if (playground && !shared) {
        // The anonymous playground persists this store as its complete local
        // history. Keep all sessions so saving it cannot discard unloaded rows.
        const { data } = await getMessages(id, { order: "DESC" });
        return { messages: data };
      }
      const { data } = await getMessages(id, {
        ...(sessionId ? { session_id: sessionId } : {}),
        // One lookahead row detects the last page without a count or an empty-page click.
        limit: PAGE_SIZE + 1,
        offset: pageParam,
        order: "DESC",
      });
      return {
        messages: data.slice(0, PAGE_SIZE),
        nextOffset: data.length > PAGE_SIZE ? pageParam + PAGE_SIZE : undefined,
      };
    },
    getNextPageParam: (page) => page.nextOffset,
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
