import { queryClient } from "@/contexts";
import type { Message } from "@/types/messages";

export const updateMessage = (updatedMessage: Message) => {
  queryClient.setQueryData(
    [
      "useGetMessagesQuery",
      { id: updatedMessage.flow_id, session_id: updatedMessage.session_id },
    ],
    (old: Message[]) => {
      const newMessage = { ...updatedMessage };
      if (newMessage.properties?.state === "partial") {
        newMessage.text =
          (old.find((message) => message.id === updatedMessage.id)?.text ||
            "") + (newMessage.text || "");
      } else {
        newMessage.text = updatedMessage.text;
      }
      return (
        old.find((message) => message.id === newMessage.id)
          ? old.map((message) =>
              message.id === newMessage.id ? newMessage : message,
            )
          : [...old, newMessage]
      ).filter((message) => message.id !== null);
    },
  );
};

export const addUserMessage = (updatedMessage: Message) => {
  queryClient.setQueryData(
    [
      "useGetMessagesQuery",
      { id: updatedMessage.flow_id, session_id: updatedMessage.session_id },
    ],
    (old: Message[]) => {
      return [...old, updatedMessage];
    },
  );
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
    (old: Message[]) => {
      return old.filter(
        (message) => !removedMessages.some((m) => m === message.id),
      );
    },
  );
};
