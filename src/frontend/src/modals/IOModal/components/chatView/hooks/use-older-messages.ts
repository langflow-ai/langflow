import { useCallback, useEffect, useRef, useState } from "react";
import {
  getMessages,
  MESSAGE_HISTORY_PAGE_SIZE,
} from "@/controllers/API/queries/messages";
import { useMessagesStore } from "@/stores/messagesStore";
import type { Message } from "@/types/messages";

/**
 * Scroll-up pagination for the shared playground's chat history.
 *
 * History reads are bounded, so this view opens on the newest page and pages
 * backwards on demand. Older messages are merged into the messages store, which
 * is what the view renders from.
 */
export const useOlderMessages = (
  flowId: string | undefined,
  visibleSession: string | null | undefined,
) => {
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  // Anchored to the number of rows fetched, not to the store length: live
  // messages are appended to the store while the user is paging.
  const offsetRef = useRef(0);
  const loadingRef = useRef(false);

  useEffect(() => {
    setHasMore(true);
    offsetRef.current = 0;
  }, [flowId, visibleSession]);

  const loadMore = useCallback(async (): Promise<number> => {
    if (loadingRef.current || !hasMore || !flowId) return 0;
    loadingRef.current = true;
    setIsLoadingMore(true);
    try {
      // Loop until a page brings something new or history runs out: the view
      // opens on the newest page, so the first page this fetches is already in
      // the store and dedup would otherwise return 0 and stall the trigger —
      // it only re-fires once prepended messages move the scroll position.
      let prepended = 0;
      let exhausted = false;
      while (prepended === 0 && !exhausted) {
        const response = await getMessages(flowId, {
          ...(visibleSession ? { session_id: visibleSession } : {}),
          limit: MESSAGE_HISTORY_PAGE_SIZE,
          order: "DESC",
          offset: offsetRef.current,
        });
        const olderMessages: Message[] = response.data || [];

        exhausted = olderMessages.length < MESSAGE_HISTORY_PAGE_SIZE;
        if (olderMessages.length === 0) break;
        // Advance by what the server returned, so a page made entirely of
        // messages already in the store still moves the cursor forward.
        offsetRef.current += olderMessages.length;

        const store = useMessagesStore.getState();
        const knownIds = new Set(store.messages.map((message) => message.id));
        const newMessages = olderMessages.filter(
          (message) => !knownIds.has(message.id),
        );
        if (newMessages.length > 0) {
          store.setMessages([...newMessages, ...store.messages]);
          prepended = newMessages.length;
        }
      }
      if (exhausted) setHasMore(false);
      return prepended;
    } catch (error) {
      console.error("Failed to load older messages:", error);
      setHasMore(false);
      return 0;
    } finally {
      loadingRef.current = false;
      setIsLoadingMore(false);
    }
  }, [flowId, hasMore, visibleSession]);

  return { loadMore, hasMore, isLoadingMore };
};
