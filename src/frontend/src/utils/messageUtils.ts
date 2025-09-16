import { queryClient } from "@/contexts";
import type { Message } from "@/types/messages";

export const updateMessage = (updatedMessage: Message) => {
  queryClient.setQueryData(
    [
      "useGetMessagesQuery",
      { id: updatedMessage.flow_id, session_id: updatedMessage.session_id },
    ],
    (old: Message[]) => {
      return old.find((message) => message.id === updatedMessage.id)
        ? old.map((message) =>
            message.id === updatedMessage.id ? updatedMessage : message,
          )
        : [...old, updatedMessage];
    },
  );
};

export const removeMessage = (removedMessage: Message) => {
  queryClient.setQueryData(
    [
      "useGetMessagesQuery",
      { id: removedMessage.flow_id, session_id: removedMessage.session_id },
    ],
    (old: Message[]) => {
      return old.filter((message) => message.id !== removedMessage.id);
    },
  );
};
