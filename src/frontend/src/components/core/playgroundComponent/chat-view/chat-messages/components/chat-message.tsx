import { useEffect, useState } from "react";
import { ErrorView } from "@/components/core/playgroundComponent/chat-view/chat-messages/components/error-message";
import { UserMessage } from "@/components/core/playgroundComponent/chat-view/chat-messages/components/user-message";
import useFlowStore from "@/stores/flowStore";
import { ContentBlock, JSONObject } from "@/types/chat";
import type { chatMessagePropsType } from "@/types/components";
import { BotMessage } from "./bot-message";

export default function ChatMessage({
  chat,
  lastMessage,
  updateChat,
  closeChat,
  playgroundPage,
}: chatMessagePropsType): JSX.Element {
  const fitViewNode = useFlowStore((state) => state.fitViewNode);
  const [showError, setShowError] = useState(false);

  // Handle error display delay
  useEffect(() => {
    if (chat.category === "error") {
      const timer = setTimeout(() => {
        setShowError(true);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [chat.category]);

  // Error messages
  if (chat.category === "error") {
    const blocks = (chat.content_blocks ?? []) as Array<
      ContentBlock | Record<string, JSONObject>
    >;
    return (
      <ErrorView
        blocks={blocks}
        showError={showError}
        lastMessage={lastMessage}
        closeChat={closeChat}
        fitViewNode={fitViewNode}
        chat={chat}
      />
    );
  }

  // Check if message is empty (would show "No input message provided")
  const chatMessage = chat.message ? chat.message.toString() : "";
  const isEmpty = chatMessage.trim() === "";

  // User messages (but treat empty messages as bot messages)
  if (chat.isSend && !isEmpty) {
    return (
      <UserMessage
        chat={chat}
        lastMessage={lastMessage}
        updateChat={updateChat}
        closeChat={closeChat}
        playgroundPage={playgroundPage}
      />
    );
  }

  // Bot messages (and empty user messages)
  return (
    <BotMessage
      chat={chat}
      lastMessage={lastMessage}
      updateChat={updateChat}
      closeChat={closeChat}
      playgroundPage={playgroundPage}
    />
  );
}
