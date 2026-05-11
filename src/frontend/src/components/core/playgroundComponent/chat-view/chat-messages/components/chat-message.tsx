import { useEffect, useState } from "react";
import useFlowStore from "@/stores/flowStore";
import type { chatMessagePropsType } from "@/types/components";
import { BotMessage } from "./bot-message";
import { ErrorView } from "./error-message";
import { UserMessage } from "./user-message";

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
    const blocks = chat.content_blocks ?? [];
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
  const hasFiles = chat.files && chat.files.length > 0;

  // User messages (show if has text OR has files)
  if (chat.isSend && (!isEmpty || hasFiles)) {
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
