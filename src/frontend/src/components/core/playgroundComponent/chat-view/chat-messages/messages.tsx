import { useEffect, useMemo, useRef } from "react";
import { StickToBottom } from "use-stick-to-bottom";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { ChatMessageType } from "@/types/chat";
import { cn } from "@/utils/utils";
import { BotMessage } from "./components/bot-message";
import ChatMessage from "./components/chat-message";
import { useChatHistory } from "./hooks/use-chat-history";

interface MessagesProps {
  visibleSession: string | null;
  playgroundPage?: boolean;
  updateChat?: (chat: ChatMessageType, message: string) => void;
  closeChat?: () => void;
}

export const Messages = ({
  visibleSession,
  playgroundPage,
  updateChat,
  closeChat,
}: MessagesProps) => {
  const chatHistory = useChatHistory(visibleSession);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const isPlaygroundOpen = usePlaygroundStore((state) => state.isOpen);

  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // Always scroll to bottom when new messages arrive or thinking starts
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chatHistory.length, isBuilding]);

  // Show thinking placeholder when building and last message is from user (no bot response yet)
  const lastChat = chatHistory[chatHistory.length - 1];
  const showThinkingPlaceholder = isBuilding && lastChat?.isSend === true;

  const thinkingPlaceholder = useMemo<ChatMessageType>(
    () => ({
      id: "thinking-placeholder",
      message: "",
      isSend: false,
      sender_name: "AI",
      category: "message",
      content_blocks: [],
      timestamp: new Date().toISOString(),
    }),
    [],
  );

  const messagesContent = (
    <div className="flex flex-col flex-grow place-self-center w-full relative overflow-x-hidden @[70rem]/chat-panel:pl-[75px] pl-0">
      {chatHistory && (isBuilding || chatHistory.length > 0) && (
        <>
          {chatHistory.map((chat: ChatMessageType, index) => {
            return (
              <ChatMessage
                key={`${chat.id}-${index}`}
                chat={chat}
                lastMessage={
                  !showThinkingPlaceholder && chatHistory.length - 1 === index
                }
                updateChat={updateChat ?? (() => {})}
                closeChat={closeChat}
                playgroundPage={playgroundPage}
              />
            );
          })}
          {showThinkingPlaceholder && (
            <BotMessage
              chat={thinkingPlaceholder}
              lastMessage={true}
              updateChat={updateChat ?? (() => {})}
              closeChat={closeChat}
              playgroundPage={playgroundPage}
            />
          )}
          {isPlaygroundOpen && (
            <div
              ref={bottomRef}
              className="pointer-events-none absolute bottom-0 left-0 right-0 h-0 w-0 overflow-hidden"
              aria-hidden
            />
          )}
        </>
      )}
    </div>
  );

  return (
    <StickToBottom
      className={cn(
        "flex w-full flex-col rounded-md",
        visibleSession ? "h-[95%]" : "h-full",
      )}
      resize="smooth"
      initial="instant"
      mass={1}
    >
      <StickToBottom.Content className="flex flex-col min-h-full">
        {messagesContent}
      </StickToBottom.Content>
    </StickToBottom>
  );
};
