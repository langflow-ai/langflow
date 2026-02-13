import { queryClient } from "@/contexts";
import useFlowStore from "@/stores/flowStore";
import type { Message } from "@/types/messages";
import {
  removePlaygroundSessionMessages,
  savePlaygroundMessages,
} from "@/utils/playground-storage";

const MESSAGES_QUERY_KEY = "useGetMessagesQuery";
const BOT_SENDER = "Machine";

const syncToPlaygroundStorage = (flowId: string): void => {
  if (!useFlowStore.getState().playgroundPage) return;
  const seen = new Set<string>();
  const unique: Message[] = [];
  for (const query of queryClient.getQueryCache().getAll()) {
    const key = query.queryKey;
    if (!Array.isArray(key) || key[0] !== MESSAGES_QUERY_KEY) continue;
    const params = key[1] as { id?: string; session_id?: string } | undefined;
    if (params?.id !== flowId || !params.session_id) continue;
    for (const msg of (query.state.data as Message[]) ?? []) {
      if (msg.id !== null && !seen.has(msg.id)) {
        seen.add(msg.id);
        unique.push(msg);
      }
    }
  }
  savePlaygroundMessages(flowId, unique);
};

const findMessageContext = (
  messageId: string | null,
): { flow_id?: string; session_id?: string } | null => {
  if (!messageId) return null;

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
  // Streaming tokens may lack flow_id/session_id — recover from existing cache entry
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

  if (!flowId || !sessionId) {
    console.warn(
      "updateMessage: Missing flow_id or session_id",
      updatedMessage,
    );
    return;
  }

  const cacheKey = [MESSAGES_QUERY_KEY, { id: flowId, session_id: sessionId }];

  queryClient.ensureQueryData({
    queryKey: cacheKey,
    queryFn: () => [],
  });

  queryClient.setQueryData(cacheKey, (old: Message[] = []) => {
    const newMessage = { ...updatedMessage };
    const isStreamingToken = newMessage.properties?.state === "partial";

    const existingMessage = old.find(
      (message) => message.id === updatedMessage.id,
    );

    // Streaming tokens accumulate text; non-streaming replace completely
    if (isStreamingToken && existingMessage) {
      newMessage.text = (existingMessage.text || "") + (newMessage.text || "");
      newMessage.sender = existingMessage.sender || newMessage.sender;
      newMessage.sender_name =
        existingMessage.sender_name || newMessage.sender_name;
      newMessage.timestamp = existingMessage.timestamp || newMessage.timestamp;
      newMessage.files = existingMessage.files || newMessage.files;
    } else if (isStreamingToken && !existingMessage) {
      if (!newMessage.id) {
        console.warn("updateMessage: First token missing id", updatedMessage);
        return old;
      }
      newMessage.text = newMessage.text || "";
    }

    // Real user messages replace their placeholder (null-id entry)
    if (newMessage.sender === "User" && newMessage.id) {
      const placeholderIndex = old.findIndex(
        (msg) =>
          msg.id === null &&
          msg.session_id === newMessage.session_id &&
          msg.sender === newMessage.sender,
      );

      if (placeholderIndex !== -1) {
        const result = old.filter((_, idx) => idx !== placeholderIndex);
        const existingIndex = result.findIndex(
          (message) => message.id === newMessage.id,
        );
        if (existingIndex !== -1) {
          return result.map((msg, idx) =>
            idx === existingIndex ? newMessage : msg,
          );
        } else {
          return [...result, newMessage];
        }
      }
    }

    const existingIndex = old.findIndex(
      (message) => message.id === newMessage.id,
    );
    if (existingIndex !== -1) {
      return old.map((msg, idx) => (idx === existingIndex ? newMessage : msg));
    } else {
      if (newMessage.id === null || newMessage.id) {
        return [...old, newMessage];
      }
      return old;
    }
  });

  if (updatedMessage.properties?.state !== "partial") {
    syncToPlaygroundStorage(flowId);
  }
};

export const addUserMessage = (updatedMessage: Message) => {
  const cacheKey = [
    MESSAGES_QUERY_KEY,
    { id: updatedMessage.flow_id, session_id: updatedMessage.session_id },
  ];

  queryClient.ensureQueryData({
    queryKey: cacheKey,
    queryFn: () => [],
  });

  queryClient.setQueryData(cacheKey, (old: Message[] = []) => {
    return [...old, updatedMessage];
  });

  syncToPlaygroundStorage(updatedMessage.flow_id);
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

  syncToPlaygroundStorage(flowId);
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

  queryClient.setQueryData(
    [MESSAGES_QUERY_KEY, { id: flowId, session_id: sessionId }],
    () => [],
  );

  const mainQueryKey = [MESSAGES_QUERY_KEY, { id: flowId }];
  const mainCache = queryClient.getQueryData<{ rows?: { data?: Message[] } }>(
    mainQueryKey,
  );

  if (mainCache?.rows?.data) {
    const filteredMessages = mainCache.rows.data.filter((msg) => {
      if (msg.flow_id !== flowId) return true;
      if (isDefaultSession) {
        return msg.session_id !== null && msg.session_id !== sessionId;
      }
      return msg.session_id !== sessionId;
    });

    queryClient.setQueryData(mainQueryKey, {
      ...mainCache,
      rows: {
        ...mainCache.rows,
        data: filteredMessages,
      },
    });
  }

  queryClient.removeQueries({
    queryKey: [MESSAGES_QUERY_KEY, { id: flowId, session_id: sessionId }],
  });

  if (useFlowStore.getState().playgroundPage) {
    removePlaygroundSessionMessages(flowId, sessionId);
  }
};
