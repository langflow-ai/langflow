import { Fragment, memo, useEffect, useRef } from "react";
import { StickToBottom } from "use-stick-to-bottom";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { ChatMessageType } from "@/types/chat";
import { cn } from "@/utils/utils";
import ChatMessage from "./components/chat-message";
import ThinkingMessage from "./components/thinking-message";
import { useChatHistory } from "./hooks/use-chat-history";
import {
  useThinkingDurationStore,
  useTrackThinkingDuration,
} from "./hooks/use-thinking-duration";

interface MessagesProps {
  visibleSession: string | null;
  playgroundPage?: boolean;
  updateChat?: (chat: ChatMessageType, message: string) => void;
  closeChat?: () => void;
}

const MemoizedChatMessage = memo(ChatMessage, (prevProps, nextProps) => {
  return (
    prevProps.chat.message === nextProps.chat.message &&
    prevProps.chat.id === nextProps.chat.id &&
    prevProps.chat.session === nextProps.chat.session &&
    prevProps.chat.content_blocks === nextProps.chat.content_blocks &&
    prevProps.chat.properties === nextProps.chat.properties &&
    prevProps.lastMessage === nextProps.lastMessage
  );
});

export const Messages = ({
  visibleSession,
  playgroundPage,
  updateChat,
  closeChat,
}: MessagesProps) => {
  const chatHistory = useChatHistory(visibleSession);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const duration = useThinkingDurationStore((state) => state.duration);
  const isPlaygroundOpen = usePlaygroundStore((state) => state.isOpen);

  // Track thinking duration at this level so it persists even when ThinkingMessage unmounts
  useTrackThinkingDuration(isBuilding);

  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // Always scroll to bottom when new messages arrive or thinking starts
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chatHistory.length, isBuilding]);

  const messagesContent = (
    <div className="flex flex-col flex-grow place-self-center w-full relative overflow-x-hidden">
      {chatHistory && (isBuilding || chatHistory.length > 0) && (
        <>
          {chatHistory.map((chat, index) => {
            const isLastMessage = chatHistory.length - 1 === index;
            const isLastUserMessage =
              isLastMessage && chat.isSend && isBuilding;
            return (
              <Fragment key={`${chat.id}-${index}`}>
                <MemoizedChatMessage
                  chat={chat}
                  lastMessage={isLastMessage}
                  updateChat={updateChat}
                  closeChat={closeChat}
                  playgroundPage={playgroundPage}
                  isThinking={false}
                  thinkingDuration={duration}
                />
                {isLastUserMessage && (
                  <ThinkingMessage isThinking={isBuilding} duration={null} />
                )}
              </Fragment>
            );
          })}
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
