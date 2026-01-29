import { queryClient } from "@/contexts";
import type { Message } from "@/types/messages";

const MESSAGES_QUERY_KEY = "useGetMessagesQuery";
const BOT_SENDER = "Machine";

// Helper to find flow_id and session_id from existing message with same ID
const findMessageContext = (
  messageId: string | null,
): { flow_id?: string; session_id?: string } | null => {
  if (!messageId) return null;

  // Search all queries in cache for a message with this ID
  const cache = queryClient.getQueryCache();
  const queries = cache.getAll();

  for (const query of queries) {
    const queryKey = query.queryKey;
    if (Array.isArray(queryKey) && queryKey[0] === MESSAGES_QUERY_KEY) {
      const messages = query.state.data as Message[] | undefined;
      if (Array.isArray(messages)) {
        const found = messages.find((msg) => msg.id === messageId);
        if (found && found.flow_id && found.session_id) {
          return { flow_id: found.flow_id, session_id: found.session_id };
        }
      }
    }
  }
  return null;
};

export const updateMessage = (updatedMessage: Message) => {
  // For streaming tokens, if flow_id/session_id are missing, try to find from existing message
  let flowId = updatedMessage.flow_id;
  let sessionId = updatedMessage.session_id;

  if (
    (!flowId || !sessionId) &&
    updatedMessage.id &&
    updatedMessage.properties?.state === "partial"
  ) {
    const context = findMessageContext(updatedMessage.id);
    if (context) {
      flowId = flowId || context.flow_id || "";
      sessionId = sessionId || context.session_id || "";
      updatedMessage.flow_id = flowId;
      updatedMessage.session_id = sessionId;
    }
  }

  // Validate required fields for cache key
  if (!flowId || !sessionId) {
    console.warn(
      "updateMessage: Missing flow_id or session_id",
      updatedMessage,
    );
    return;
  }

  const cacheKey = [MESSAGES_QUERY_KEY, { id: flowId, session_id: sessionId }];

  // Ensure the query exists in cache first
  queryClient.ensureQueryData({
    queryKey: cacheKey,
    queryFn: () => [],
  });

  // Update the cache directly
  queryClient.setQueryData(cacheKey, (old: Message[] = []) => {
    const newMessage = { ...updatedMessage };
    const isStreamingToken = newMessage.properties?.state === "partial";

    // Find existing message
    const existingMessage = old.find(
      (message) => message.id === updatedMessage.id,
    );

    // For streaming tokens ONLY, accumulate text
    if (isStreamingToken && existingMessage) {
      // Accumulate text for existing streaming message
      newMessage.text = (existingMessage.text || "") + (newMessage.text || "");
      // Preserve other fields from existing message
      newMessage.sender = existingMessage.sender || newMessage.sender;
      newMessage.sender_name =
        existingMessage.sender_name || newMessage.sender_name;
      newMessage.timestamp = existingMessage.timestamp || newMessage.timestamp;
      newMessage.files = existingMessage.files || newMessage.files;
    } else if (isStreamingToken && !existingMessage) {
      // First token - ensure we have all required fields
      if (!newMessage.id) {
        console.warn("updateMessage: First token missing id", updatedMessage);
        return old; // Don't add message without ID
      }
      // Initialize text if empty
      newMessage.text = newMessage.text || "";
    }
    // For non-streaming messages (add_message), always replace completely - don't accumulate

    // If this is a real user message, remove matching placeholder
    if (newMessage.sender === "User" && newMessage.id) {
      const placeholderIndex = old.findIndex(
        (msg) =>
          msg.id === null &&
          msg.session_id === newMessage.session_id &&
          msg.sender === newMessage.sender,
      );

      if (placeholderIndex !== -1) {
        // Remove placeholder and add/update real message
        const result = old.filter((_, idx) => idx !== placeholderIndex);
        const existingIndex = result.findIndex(
          (message) => message.id === newMessage.id,
        );
        if (existingIndex !== -1) {
          // Update existing message
          return result.map((msg, idx) =>
            idx === existingIndex ? newMessage : msg,
          );
        } else {
          // Add new message
          return [...result, newMessage];
        }
      }
    }

    // Update existing message or add new one
    const existingIndex = old.findIndex(
      (message) => message.id === newMessage.id,
    );
    if (existingIndex !== -1) {
      // Update existing message - create new array to trigger reactivity
      return old.map((msg, idx) => (idx === existingIndex ? newMessage : msg));
    } else {
      // Add new message - only if it has an ID (or is a placeholder)
      if (newMessage.id === null || newMessage.id) {
        return [...old, newMessage];
      }
      // Skip messages without ID (except placeholders)
      return old;
    }
  });

  // setQueryData automatically notifies observers - no need to invalidate
};

export const addUserMessage = (updatedMessage: Message) => {
  const cacheKey = [
    MESSAGES_QUERY_KEY,
    { id: updatedMessage.flow_id, session_id: updatedMessage.session_id },
  ];

  // Ensure query exists
  queryClient.ensureQueryData({
    queryKey: cacheKey,
    queryFn: () => [],
  });

  // Add placeholder to cache
  queryClient.setQueryData(cacheKey, (old: Message[] = []) => {
    return [...old, updatedMessage];
  });

  // setQueryData automatically notifies observers - no need to invalidate
};

export const updateMessages = (updatedMessages: Message[]) => {
  queryClient.setQueryData(
    [
      MESSAGES_QUERY_KEY,
      {
        id: updatedMessages[0].flow_id,
        session_id: updatedMessages[0].session_id,
      },
    ],
    (_) => {
      return updatedMessages.filter((message) => message.id !== null);
    },
  );
};

export const removeMessages = (
  removedMessages: string[],
  sessionId: string,
  flowId: string,
) => {
  if (removedMessages.length === 0) {
    return;
  }
  queryClient.setQueryData(
    [MESSAGES_QUERY_KEY, { id: flowId, session_id: sessionId }],
    (old: Message[] = []) => {
      return old.filter(
        (message) => !removedMessages.some((m) => m === message.id),
      );
    },
  );
};

export const findLastBotMessage = (): {
  message: Message;
  queryKey: unknown[];
} | null => {
  const cache = queryClient.getQueryCache();
  const queries = cache.getAll();

  for (const query of queries) {
    const queryKey = query.queryKey;
    if (!Array.isArray(queryKey) || queryKey[0] !== MESSAGES_QUERY_KEY) {
      continue;
    }
    const messages = query.state.data as Message[] | undefined;
    if (!Array.isArray(messages)) continue;

    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.sender === BOT_SENDER && msg.id) {
        return { message: msg, queryKey };
      }
    }
  }
  return null;
};

export const updateMessageProperties = (
  messageId: string,
  queryKey: unknown[],
  properties: Record<string, unknown>,
) => {
  queryClient.setQueryData(queryKey, (old: Message[] = []) =>
    old.map((msg) =>
      msg.id === messageId
        ? { ...msg, properties: { ...msg.properties, ...properties } }
        : msg,
    ),
  );
};

export const clearSessionMessages = (sessionId: string, flowId: string) => {
  const isDefaultSession = sessionId === flowId;

  // Clear session-specific cache immediately
  queryClient.setQueryData(
    [MESSAGES_QUERY_KEY, { id: flowId, session_id: sessionId }],
    () => [],
  );

  // For default session, also clear messages with null session_id (legacy)
  if (isDefaultSession) {
    // Get all messages from the main query cache and filter out default session messages
    const mainQueryKey = [MESSAGES_QUERY_KEY, { id: flowId }];
    const mainCache = queryClient.getQueryData<{ rows?: { data?: Message[] } }>(
      mainQueryKey,
    );

    if (mainCache?.rows?.data) {
      // Filter out messages that belong to default session (including null session_id)
      const filteredMessages = mainCache.rows.data.filter((msg) => {
        // Keep messages that don't belong to this flow or have a different session_id
        if (msg.flow_id !== flowId) return true;
        // For default session, remove messages with null session_id or matching session_id
        return msg.session_id !== null && msg.session_id !== sessionId;
      });

      // Update the main cache without invalidating (to prevent refetch)
      queryClient.setQueryData(mainQueryKey, {
        ...mainCache,
        rows: {
          ...mainCache.rows,
          data: filteredMessages,
        },
      });
    }
  }

  // Remove queries instead of invalidating to prevent refetch that brings messages back
  // The cache is already cleared above, so we just need to remove the query entries
  queryClient.removeQueries({
    queryKey: [MESSAGES_QUERY_KEY, { id: flowId, session_id: sessionId }],
  });

  // For the main query, we keep it but with filtered data (already updated above)
  // Only invalidate if we need to refetch (but not immediately to avoid race condition)
};
