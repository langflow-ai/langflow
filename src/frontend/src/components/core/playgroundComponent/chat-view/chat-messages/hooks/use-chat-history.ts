import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useGetFlowId } from "@/components/core/playgroundComponent/hooks/use-get-flow-id";
import {
  getMessages,
  useGetMessagesQuery,
} from "@/controllers/API/queries/messages";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import type { ChatMessageType } from "@/types/chat";
import type { Message } from "@/types/messages";
import { isMessageForSession } from "../../utils/session-filter";
import sortSenderMessages from "../utils/sort-sender-messages";

export const useChatHistory = (visibleSession: string | null) => {
  const currentFlowId = useGetFlowId();
  const queryClient = useQueryClient();
  const isPlaygroundOpen = usePlaygroundStore((state) => state.isOpen);

  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  // Pagination offset anchored to fetched count — the cache length drifts
  // as live messages are appended.
  const offsetRef = useRef(0);

  // Reset pagination when session or flow changes
  useEffect(() => {
    setHasMore(true);
    offsetRef.current = 0;
  }, [visibleSession, currentFlowId]);

  // Fetch messages from backend only when playground is visible and cap at 20
  // to prevent unbounded state growth that causes canvas re-render slowdown.
  const messageQueryParams: Parameters<typeof useGetMessagesQuery>[0] = {
    id: currentFlowId,
    mode: "union",
    params: { limit: 20, order: "DESC" },
  };
  const { data: queryData } = useGetMessagesQuery(messageQueryParams, {
    enabled: isPlaygroundOpen,
  });

  // Session cache key - this is the single source of truth for messages
  const sessionCacheKey = useMemo(
    () => [
      "useGetMessagesQuery",
      { id: currentFlowId, session_id: visibleSession },
    ],
    [currentFlowId, visibleSession],
  );

  // Watch the session cache - this automatically updates when updateMessage/addUserMessage change it
  const { data: sessionMessages = [] } = useQuery<Message[]>({
    queryKey: sessionCacheKey,
    queryFn: () => {
      // Return cached data immediately - this makes the query active and reactive
      // We're using useQuery purely as a subscription mechanism, not for fetching
      const cachedData =
        queryClient.getQueryData<Message[]>(sessionCacheKey) || [];
      return cachedData;
    },
    staleTime: Infinity, // Never refetch - updates come from setQueryData, not server
    gcTime: 5 * 60 * 1000, // Keep in cache for 5 minutes (allows cleanup of old sessions)
    structuralSharing: false, // Detect all changes including text updates during streaming
    refetchOnMount: false,
    refetchOnWindowFocus: false,
  });

  // Initialize cache with backend messages on first load (only if cache is empty)
  useEffect(() => {
    if (queryData && typeof queryData === "object" && "rows" in queryData) {
      const rowsData = queryData.rows as { data?: Message[] } | undefined;
      if (rowsData && typeof rowsData === "object" && "data" in rowsData) {
        const backendMessages = (rowsData.data || []).filter((msg: Message) =>
          isMessageForSession(msg, currentFlowId, visibleSession),
        );

        const existingCache =
          queryClient.getQueryData<Message[]>(sessionCacheKey) || [];

        // Only initialize if cache is empty and we have backend messages for this session
        if (existingCache.length === 0 && backendMessages.length > 0) {
          queryClient.setQueryData(sessionCacheKey, backendMessages);
          offsetRef.current = backendMessages.length;
        }
      }
    }
  }, [queryData, queryClient, sessionCacheKey, currentFlowId, visibleSession]);

  // Load older messages (scroll-up pagination). Returns how many messages
  // were actually prepended.
  const loadMore = useCallback(async (): Promise<number> => {
    if (isLoadingMore || !hasMore || !currentFlowId) return 0;
    setIsLoadingMore(true);
    try {
      // Loop until at least one new message lands or pages run out: after a
      // remount offsetRef restarts at 0 while the cache may already hold the
      // early pages, and dedup would otherwise swallow them and stall.
      let prepended = 0;
      while (prepended === 0) {
        const response = await getMessages(currentFlowId, {
          ...(visibleSession ? { session_id: visibleSession } : {}),
          limit: 20,
          order: "DESC",
          offset: offsetRef.current,
        });
        const olderMessages: Message[] = response.data || [];
        offsetRef.current += olderMessages.length;

        const exhausted = olderMessages.length < 20;
        if (exhausted) {
          setHasMore(false);
        }

        if (olderMessages.length > 0) {
          const existing =
            queryClient.getQueryData<Message[]>(sessionCacheKey) || [];
          // The flow-level seed fetch and session-scoped pages can overlap.
          const existingIds = new Set(existing.map((m) => m.id));
          const deduped = olderMessages.filter((m) => !existingIds.has(m.id));
          if (deduped.length > 0) {
            queryClient.setQueryData(sessionCacheKey, [
              ...deduped,
              ...existing,
            ]);
            prepended = deduped.length;
          }
        }

        if (exhausted) break;
      }
      return prepended;
    } catch (e) {
      console.error("Failed to load more messages:", e);
      return 0;
    } finally {
      setIsLoadingMore(false);
    }
  }, [
    isLoadingMore,
    hasMore,
    currentFlowId,
    visibleSession,
    sessionCacheKey,
    queryClient,
  ]);

  // Use session cache as the single source of truth
  // updateMessage and addUserMessage handle all updates (placeholders, streaming, etc.)
  const messages = sessionMessages;

  // Filter and transform messages for display
  const chatHistory = useMemo(() => {
    // Filter messages for current session
    const filteredMessages: ChatMessageType[] = messages
      .filter((message: Message) =>
        isMessageForSession(message, currentFlowId, visibleSession),
      )
      .map((message: Message): ChatMessageType => {
        let files = message.files;
        // Handle the "[]" case, empty string, or already parsed array
        if (Array.isArray(files)) {
          // files is already an array, no need to parse
        } else if (files === "[]" || files === "") {
          files = [];
        } else if (typeof files === "string") {
          try {
            files = JSON.parse(files);
          } catch (error) {
            console.error("Error parsing files:", error);
            files = [];
          }
        }
        const messageText = message.text || "";

        // Convert Message.properties to ChatMessageType.properties (PropertiesType)
        // Properties are now properly typed in Message, no cast needed
        let properties: ChatMessageType["properties"];
        if (message.properties) {
          properties = {
            ...(message.properties.source?.id && {
              source: {
                id: message.properties.source.id,
                display_name: message.properties.source.display_name || "",
                source: message.properties.source.source || "",
              },
            }),
            state: message.properties.state,
            icon: message.properties.icon,
            background_color: message.properties.background_color,
            text_color: message.properties.text_color,
            targets: message.properties.targets,
            edited: message.properties.edited,
            allow_markdown: message.properties.allow_markdown,
            positive_feedback: message.properties.positive_feedback,
            build_duration: message.properties.build_duration,
            usage: message.properties.usage,
          };
        }

        return {
          isSend: message.sender === "User",
          message: messageText,
          sender_name: message.sender_name,
          files: files,
          id: message.id || "",
          timestamp: message.timestamp,
          session: message.session_id,
          flow_id: message.flow_id,
          edit: message.edit,
          background_color: message.background_color,
          text_color: message.text_color,
          content_blocks: message.content_blocks,
          category: message.category,
          properties: properties,
        };
      });

    const sorted = [...filteredMessages].sort(sortSenderMessages);
    return sorted;
  }, [messages, visibleSession, currentFlowId]);

  return { chatHistory, loadMore, hasMore, isLoadingMore };
};
