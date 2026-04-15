import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { useGetFlowId } from "@/components/core/playgroundComponent/hooks/use-get-flow-id";
import { useGetMessagesQuery } from "@/controllers/API/queries/messages";
import type { ChatMessageType } from "@/types/chat";
import type { Message } from "@/types/messages";
import { isMessageForSession } from "../../utils/session-filter";
import sortSenderMessages from "../utils/sort-sender-messages";

export const useChatHistory = (visibleSession: string | null) => {
  const currentFlowId = useGetFlowId();
  const queryClient = useQueryClient();

  // Fetch messages from backend for initial load
  const messageQueryParams: Parameters<typeof useGetMessagesQuery>[0] = {
    id: currentFlowId,
    mode: "union",
  };
  const { data: queryData } = useGetMessagesQuery(messageQueryParams);

  // Session cache key - this is the single source of truth for messages
  const sessionCacheKey = [
    "useGetMessagesQuery",
    { id: currentFlowId, session_id: visibleSession },
  ];

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
        }
      }
    }
  }, [queryData, queryClient, sessionCacheKey, currentFlowId, visibleSession]);

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
        let properties: ChatMessageType["properties"] = undefined;
        if (message.properties?.source?.id) {
          properties = {
            source: {
              id: message.properties.source.id,
              display_name: message.properties.source.display_name || "",
              source: message.properties.source.source || "",
            },
            state: message.properties.state,
            icon: message.properties.icon,
            background_color: message.properties.background_color,
            text_color: message.properties.text_color,
            targets: message.properties.targets,
            edited: message.properties.edited,
            allow_markdown: message.properties.allow_markdown,
            positive_feedback: message.properties.positive_feedback,
            build_duration: message.properties.build_duration,
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

  return chatHistory;
};
