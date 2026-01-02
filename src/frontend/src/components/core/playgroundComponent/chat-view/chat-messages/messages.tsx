import { memo, useMemo } from "react";
import { StickToBottom } from "use-stick-to-bottom";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import { TextEffectPerChar } from "@/components/ui/textAnimation";
import useFlowStore from "@/stores/flowStore";
import { useMessagesStore } from "@/stores/messagesStore";
import { cn } from "@/utils/utils";
import ChatMessage from "./components/chat-message";
import FlowRunningSqueleton from "./components/flow-running-squeleton";
import { useChatHistory } from "./hooks/use-chat-history";
import type { ChatMessageType } from "./types";

interface MessagesProps {
  visibleSession: string | null;
  playgroundPage?: boolean;
  updateChat?: (
    chat: ChatMessageType,
    message: string,
    stream_url?: string,
  ) => void;
  closeChat?: () => void;
}

const areFilesEqual = (
  a: ChatMessageType["files"],
  b: ChatMessageType["files"],
) => {
  if (a === b) return true;
  if (!Array.isArray(a) || !Array.isArray(b)) return false;
  if (a.length !== b.length) return false;
  return a.every((file, idx) => file === b[idx]);
};

const primitiveFields: Array<keyof ChatMessageType> = [
  "id",
  "message",
  "session",
  "category",
  "isSend",
  "edit",
  "sender_name",
  "timestamp",
  "content_blocks",
  "properties",
];

const areChatsEqual = (prev: ChatMessageType, next: ChatMessageType) =>
  primitiveFields.every((field) => prev[field] === next[field]) &&
  areFilesEqual(prev.files, next.files);

const MemoizedChatMessage = memo(ChatMessage, (prevProps, nextProps) => {
  return (
    areChatsEqual(prevProps.chat, nextProps.chat) &&
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
  const displayLoadingMessage = useMessagesStore(
    (state) => state.displayLoadingMessage,
  );

  const flowRunningSkeletonMemo = useMemo(() => <FlowRunningSqueleton />, []);

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
              chatHistory.map((chat, index) => (
                <MemoizedChatMessage
                  chat={chat}
                  lastMessage={chatHistory.length - 1 === index}
                  key={`${chat.id}-${index}`}
                  updateChat={updateChat ?? (() => {})}
                  closeChat={closeChat}
                  playgroundPage={playgroundPage}
                />
              ))
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
        <div
          className={
            displayLoadingMessage ? "w-full py-4 word-break-break-word" : ""
          }
        >
          {displayLoadingMessage &&
            !(chatHistory?.[chatHistory.length - 1]?.category === "error") &&
            flowRunningSkeletonMemo}
        </div>
      </StickToBottom.Content>
    </StickToBottom>
  );
};
