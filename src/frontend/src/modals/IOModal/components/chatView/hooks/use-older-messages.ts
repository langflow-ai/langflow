import { useCallback, useEffect, useRef, useState } from "react";
import {
  getMessages,
  MESSAGE_HISTORY_PAGE_SIZE,
} from "@/controllers/API/queries/messages";
import { useMessagesStore } from "@/stores/messagesStore";
import type { Message } from "@/types/messages";

// `checkDuplicateRequestAndStoreRequest` aborts a second GET to the same path
// within 300ms, so consecutive pages have to clear that window.
const DUPLICATE_REQUEST_WINDOW_MS = 350;

const isForSession = (
  message: Message,
  flowId: string | undefined,
  visibleSession: string | null | undefined,
) =>
  message.flow_id === flowId &&
  (!visibleSession || message.session_id === visibleSession);

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

  // Counts rows fetched from the server, not store length: live messages are
  // appended to the store while the user is paging. -1 means "not yet seeded".
  const offsetRef = useRef(-1);
  const loadingRef = useRef(false);

  useEffect(() => {
    setHasMore(true);
    offsetRef.current = -1;
  }, [flowId, visibleSession]);

  const loadMore = useCallback(async (): Promise<number> => {
    if (loadingRef.current || !hasMore || !flowId) return 0;
    loadingRef.current = true;
    setIsLoadingMore(true);
    try {
      if (offsetRef.current < 0) {
        // Start past the page the view opened with, so the first request
        // returns messages the store does not already hold.
        offsetRef.current = useMessagesStore
          .getState()
          .messages.filter((message) =>
            isForSession(message, flowId, visibleSession),
          ).length;
      }

      // Retry only while a page brings nothing new — the scroll trigger re-fires
      // on prepended content, so returning 0 would otherwise stall it for good.
      let prepended = 0;
      let exhausted = false;
      for (
        let attempt = 0;
        prepended === 0 && !exhausted && attempt < 5;
        attempt++
      ) {
        if (attempt > 0) {
          await new Promise((resolve) =>
            setTimeout(resolve, DUPLICATE_REQUEST_WINDOW_MS),
          );
        }
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
      // Keep hasMore set: a cancelled or failed request is transient, and
      // clearing it here would disable paging for the rest of the session.
      console.error("Failed to load older messages:", error);
      return 0;
    } finally {
      loadingRef.current = false;
      setIsLoadingMore(false);
    }
  }, [flowId, hasMore, visibleSession]);

  return { loadMore, hasMore, isLoadingMore };
};
