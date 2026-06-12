import { Loader2 } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import { SafariScrollFix } from "@/components/common/safari-scroll-fix";
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

// Placed inside StickToBottom so useStickToBottomContext is available
const LoadMoreTrigger = ({
  hasMore,
  isLoadingMore,
  onLoadMore,
}: {
  hasMore: boolean;
  isLoadingMore: boolean;
  onLoadMore: () => void;
}) => {
  const { scrollRef } = useStickToBottomContext();
  const sentinelRef = useRef<HTMLDivElement>(null);

  // Keep stable refs to avoid recreating the observer on every render
  const hasMoreRef = useRef(hasMore);
  hasMoreRef.current = hasMore;
  const isLoadingMoreRef = useRef(isLoadingMore);
  isLoadingMoreRef.current = isLoadingMore;
  const onLoadMoreRef = useRef(onLoadMore);
  onLoadMoreRef.current = onLoadMore;

  useEffect(() => {
    const sentinel = sentinelRef.current;
    const container = scrollRef.current;
    if (!sentinel || !container) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (
          entries[0].isIntersecting &&
          hasMoreRef.current &&
          !isLoadingMoreRef.current
        ) {
          onLoadMoreRef.current();
        }
      },
      { root: container, threshold: 0 },
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [scrollRef]);

  if (!hasMore) return null;

  return (
    <div
      ref={sentinelRef}
      className="flex h-8 w-full items-center justify-center"
    >
      {isLoadingMore && (
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      )}
    </div>
  );
};

export const Messages = ({
  visibleSession,
  playgroundPage,
  updateChat,
  closeChat,
}: MessagesProps) => {
  const { chatHistory, loadMore, hasMore, isLoadingMore } =
    useChatHistory(visibleSession);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const isPlaygroundOpen = usePlaygroundStore((state) => state.isOpen);

  const bottomRef = useRef<HTMLDivElement | null>(null);

  // Show thinking placeholder when building and last message is from user (no bot response yet)
  // Only show if the flow has a ChatOutput, otherwise there's nothing to produce a response
  const outputs = useFlowStore((state) => state.outputs);
  const hasChatOutput = outputs.some((output) => output.type === "ChatOutput");
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
    <div className="flex flex-col flex-grow place-self-center w-full relative overflow-x-hidden">
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
      resize="instant"
      initial="instant"
    >
      <StickToBottom.Content className="flex flex-col min-h-full ">
        {messagesContent}
      </StickToBottom.Content>
      <SafariScrollFix />
    </StickToBottom>
  );
};
