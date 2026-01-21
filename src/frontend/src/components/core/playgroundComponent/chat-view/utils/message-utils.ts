import { queryClient } from "@/contexts";
import type { Message } from "@/types/messages";

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
    if (Array.isArray(queryKey) && queryKey[0] === "useGetMessagesQuery") {
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
      flowId = flowId || context.flow_id;
      sessionId = sessionId || context.session_id;
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

  const cacheKey = [
    "useGetMessagesQuery",
    { id: flowId, session_id: sessionId },
  ];

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
    "useGetMessagesQuery",
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
      "useGetMessagesQuery",
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
    ["useGetMessagesQuery", { id: flowId, session_id: sessionId }],
    (old: Message[] = []) => {
      return old.filter(
        (message) => !removedMessages.some((m) => m === message.id),
      );
    },
  );
};

export const clearSessionMessages = (sessionId: string, flowId: string) => {
  // Clear session cache
  queryClient.setQueryData(
    ["useGetMessagesQuery", { id: flowId, session_id: sessionId }],
    () => [],
  );

  // Invalidate the main messages query to refetch from backend
  queryClient.invalidateQueries({
    queryKey: ["useGetMessagesQuery", { id: flowId }],
  });

  // Invalidate session cache watchers
  queryClient.invalidateQueries({
    queryKey: ["useGetMessagesQuery", { id: flowId, session_id: sessionId }],
  });
};
