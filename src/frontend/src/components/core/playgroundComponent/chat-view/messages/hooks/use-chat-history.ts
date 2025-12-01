import { useEffect, useState } from "react";
import { useGetMessagesQuery } from "@/controllers/API/queries/messages";
import { useMessagesStore } from "@/stores/messagesStore";
import { ChatMessageType } from "@/types/chat";
import { useGetFlowId } from "../../hooks/use-get-flow-id";
import sortSenderMessages from "../utils/sort-sender-messages";

export const useChatHistory = (visibleSession: string | null) => {
  const currentFlowId = useGetFlowId();
  const messages = useMessagesStore((state) => state.messages);
  const [chatHistory, setChatHistory] = useState<ChatMessageType[]>([]);

  // Fetch messages using the query hook to populate the store
  useGetMessagesQuery({
    id: currentFlowId,
    mode: "union", // Dummy mode, we only care about the side effect of populating the store
    params: {
      session_id: visibleSession,
    },
  });

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
      .map((message) => {
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
        return {
          isSend: message.sender === "User",
          message: message.text,
          sender_name: message.sender_name,
          files: files,
          id: message.id,
          timestamp: message.timestamp,
          session: message.session_id,
          edit: message.edit,
          background_color: message.background_color || "",
          text_color: message.text_color || "",
          content_blocks: message.content_blocks || [],
          category: message.category || "",
          properties: message.properties || {},
        };
      });

    const finalChatHistory = [...messagesFromMessagesStore].sort(
      sortSenderMessages,
    );

    setChatHistory(finalChatHistory);
  }, [messages, visibleSession, currentFlowId]);

  return chatHistory;
};
