import { useEffect, useState } from "react";
import { useGetFlowId } from "@/components/core/playgroundComponent/hooks/use-get-flow-id";
import { useGetMessagesQuery } from "@/controllers/API/queries/messages";
import { useMessagesStore } from "@/stores/messagesStore";
import type { ChatMessageType } from "@/types/chat";
import sortSenderMessages from "../utils/sort-sender-messages";

export const useChatHistory = (visibleSession: string | null) => {
  const currentFlowId = useGetFlowId();
  const messages = useMessagesStore(
    (state) => state.messages,
  ) as ChatMessageType[];
  const [chatHistory, setChatHistory] = useState<ChatMessageType[]>([]);

  // Fetch messages using the query hook to populate the store
  const messageQueryParams: Parameters<typeof useGetMessagesQuery>[0] = {
    id: currentFlowId,
  };
  useGetMessagesQuery(messageQueryParams);

  useEffect(() => {
    const messagesFromMessagesStore: ChatMessageType[] = messages
      .filter((message) => {
        const isCurrentFlow = message.flow_id === currentFlowId;
        // If visibleSession is the flow_id, it means we are in the default session
        // In the default session, we show messages that have the same session_id as the flow_id
        // OR messages that have NO session_id (legacy behavior)
        if (visibleSession === currentFlowId) {
          return (
            isCurrentFlow &&
            (message.session_id === visibleSession || !message.session_id)
          );
        }
        return isCurrentFlow && message.session_id === visibleSession;
      })
      .map((message: ChatMessageType) => {
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
        const messageText =
          typeof message.message === "string" ||
          typeof message.message === "number"
            ? message.message
            : typeof (message as { text?: unknown }).text === "string"
              ? (message as { text?: string }).text
              : "";

        return {
          isSend: message.sender === "User",
          message: messageText ?? "",
          sender_name: message.sender_name,
          files: files,
          id: message.id,
          timestamp: message.timestamp,
          session: message.session_id ?? message.session,
          flow_id: message.flow_id,
          edit: message.edit,
          background_color: message.background_color,
          text_color: message.text_color,
          content_blocks: message.content_blocks,
          category: message.category,
          properties: message.properties,
        };
      });

    const finalChatHistory = [...messagesFromMessagesStore].sort(
      sortSenderMessages,
    );

    setChatHistory(finalChatHistory);
  }, [messages, visibleSession, currentFlowId]);

  return chatHistory;
};
