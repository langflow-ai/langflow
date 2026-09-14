import { useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { StickToBottom } from "use-stick-to-bottom";
import { SafariScrollFix } from "@/components/common/safari-scroll-fix";
import { LoadMoreTrigger } from "@/shared/components/load-more-trigger";
import { ResponseCompleteStatus } from "@/shared/components/response-complete-status";
import { useResponseCompleteCue } from "@/shared/hooks/use-response-complete-cue";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import type { ChatMessageType } from "@/types/chat";
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
  const { t } = useTranslation();
  const { chatHistory, loadMore, hasMore, isLoadingMore } =
    useChatHistory(visibleSession);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const isPlaygroundOpen = usePlaygroundStore((state) => state.isOpen);

  const bottomRef = useRef<HTMLDivElement | null>(null);

  const responseCue = useResponseCompleteCue(isBuilding, chatHistory);

  // Show thinking placeholder when building and last message is from user (no bot response yet)
  // Only show if the flow has a ChatOutput, otherwise there's nothing to produce a response
  // Select the boolean, not the array: setNodes recreates `outputs` on every
  // call (including node drags), and an array subscription would re-render
  // the whole message list on each drag frame.
  const hasChatOutput = useFlowStore((state) =>
    state.outputs.some((output) => output.type === "ChatOutput"),
  );
  const lastChat = chatHistory[chatHistory.length - 1];
  const showThinkingPlaceholder =
    isBuilding && lastChat?.isSend === true && hasChatOutput;
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
    // aria-live="off" neutralizes role="log"'s implicit politeness: React
    // remounts earlier messages on send (lastMessage flips), which a live
    // list region re-announces as additions — Safari/VoiceOver read the whole
    // history on every send (LE-2041 QA). The completion cue is announced
    // solely by ResponseCompleteStatus below.
    <div
      className="flex flex-col flex-grow place-self-center w-full relative overflow-x-hidden"
      role="log"
      aria-live="off"
      aria-label={t("chat.messagesRegionLabel")}
    >
      {chatHistory && (isBuilding || chatHistory.length > 0) && (
        <>
          <LoadMoreTrigger
            hasMore={hasMore}
            isLoadingMore={isLoadingMore}
            onLoadMore={loadMore}
          />
          {chatHistory.map((chat: ChatMessageType, index) => {
            return (
              <ChatMessage
                key={chat.id}
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
      resize="instant"
      initial="instant"
    >
      <StickToBottom.Content className="flex flex-col min-h-full ">
        {messagesContent}
      </StickToBottom.Content>
      <ResponseCompleteStatus
        completedCount={responseCue.completedCount}
        completedText={responseCue.completedText}
        isAnnouncing={responseCue.isAnnouncing}
      />
      <SafariScrollFix />
    </StickToBottom>
  );
};
