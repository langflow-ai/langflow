import { memo, useMemo } from "react";
import { StickToBottom } from "use-stick-to-bottom";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import { TextEffectPerChar } from "@/components/ui/textAnimation";
import useFlowStore from "@/stores/flowStore";
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

  // Track thinking duration at this level so it persists even when ThinkingMessage unmounts
  useTrackThinkingDuration(isBuilding);

  // Find the index where we should insert the thinking message
  // It should appear after the last user message, before the bot response
  const thinkingInsertIndex = useMemo(() => {
    if (!chatHistory || chatHistory.length === 0) return -1;

    // Find the last user message index
    for (let i = chatHistory.length - 1; i >= 0; i--) {
      if (chatHistory[i].isSend) {
        // Insert after the user message
        return i + 1;
      }
    }
    return -1;
  }, [chatHistory]);

  const showThinkingMessage =
    (isBuilding || duration) &&
    chatHistory?.[chatHistory.length - 1]?.category !== "error";

  return (
    <StickToBottom
      className={cn(
        "flex h-full w-full flex-col rounded-md",
        visibleSession ? "h-[95%]" : "h-full",
      )}
      resize="smooth"
      initial="instant"
      mass={1}
    >
      <StickToBottom.Content className="flex flex-col min-h-full">
        <div className="flex flex-col flex-grow place-self-center w-full">
          {chatHistory &&
            (isBuilding || chatHistory.length > 0 ? (
              <>
                {chatHistory.map((chat, index) => {
                  // Insert thinking message after user message (before bot response)
                  const insertThinkingAfterThis =
                    showThinkingMessage &&
                    index + 1 === thinkingInsertIndex &&
                    thinkingInsertIndex < chatHistory.length;

                  return (
                    <div key={`${chat.id}-${index}`}>
                      <MemoizedChatMessage
                        chat={chat}
                        lastMessage={chatHistory.length - 1 === index}
                        updateChat={updateChat ?? (() => {})}
                        closeChat={closeChat}
                        playgroundPage={playgroundPage}
                      />
                      {insertThinkingAfterThis && (
                        <ThinkingMessage
                          isThinking={isBuilding}
                          duration={duration}
                        />
                      )}
                    </div>
                  );
                })}
                {/* If user message is the last message (no bot response yet), show at the end */}
                {showThinkingMessage &&
                  thinkingInsertIndex >= chatHistory.length && (
                    <ThinkingMessage
                      isThinking={isBuilding}
                      duration={duration}
                    />
                  )}
              </>
            ) : (
              <div className="flex flex-grow w-full flex-col items-center justify-center">
                <div className="flex flex-col items-center justify-center gap-4 p-8">
                  <LangflowLogo
                    title="Langflow logo"
                    className="h-10 w-10 scale-[1.5]"
                  />
                  <div className="flex flex-col items-center justify-center">
                    <h3 className="mt-2 pb-2 text-2xl font-semibold text-primary">
                      New chat
                    </h3>
                    <p
                      className="text-lg text-muted-foreground"
                      data-testid="new-chat-text"
                    >
                      <TextEffectPerChar>
                        Test your flow with a chat prompt
                      </TextEffectPerChar>
                    </p>
                  </div>
                </div>
              </div>
            ))}
        </div>
      </StickToBottom.Content>
    </StickToBottom>
  );
};
