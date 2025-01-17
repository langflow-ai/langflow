import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import { TextEffectPerChar } from "@/components/ui/textAnimation";
import { track } from "@/customization/utils/analytics";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import { ChatMessageType, chatViewProps } from "./types";
import { usePlaygroundStore } from "src/stores/playgroundStore";
import { useMessagesStore } from "src/stores/messageStore";
import ChatInput from "./chatInput";
import ChatMessage from "./chatMessage";
import { useFileHandler } from "src/hooks/use-file-handler";
import useDragAndDrop from "src/hooks/use-drag-and-drop";
import FlowRunningSqueleton from "../flowRunningSqueleton/flowRunningSqueleton";
import useTabVisibility from "src/hooks/use-tab-visibility";

const MemoizedChatMessage = memo(ChatMessage, (prevProps, nextProps) => {
  return (
    prevProps.chat.message === nextProps.chat.message &&
    prevProps.chat.id === nextProps.chat.id &&
    prevProps.chat.session === nextProps.chat.session &&
    prevProps.chat.content_blocks === nextProps.chat.content_blocks &&
    prevProps.chat.properties === nextProps.chat.properties
  );
});

export default function ChatView({
  sendMessage,
  lockChat,
  visibleSession,
  focusChat,
  closeChat,
  inputs,
  initialChatValue,
}: chatViewProps): JSX.Element {
  const currentFlowId = usePlaygroundStore((state) => state.currentFlowId);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessageType[] | undefined>(
    undefined,
  );
  const messages = useMessagesStore((state) => state.messages);
  const displayLoadingMessage = useMessagesStore(
    (state) => state.displayLoadingMessage,
  );

  const inputTypes = inputs.map((obj) => obj.type);
  const setChatValueStore = usePlaygroundStore((state) => state.setChatValueStore);
  const isTabHidden = useTabVisibility();

  //build chat history
  useEffect(() => {
    const messagesFromMessagesStore: ChatMessageType[] = messages
      .filter(
        (message) =>
          message.flow_id === currentFlowId &&
          (visibleSession === message.session_id || visibleSession === null),
      )
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
    const finalChatHistory = [...messagesFromMessagesStore].sort((a, b) => {
      return new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
    });

    if (messages.length === 0 && !lockChat && isTabHidden) {
      setChatValueStore(initialChatValue ?? "");
    } else {
      if(isTabHidden) {
        setChatValueStore("");
      }
    }

    setChatHistory(finalChatHistory);
  }, [messages, visibleSession, initialChatValue, lockChat, isTabHidden, currentFlowId, setChatValueStore]);
  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, []);

  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.focus();
    }
    // trigger focus on chat when new session is set
  }, [focusChat]);

  const { files, setFiles, handleFiles } = useFileHandler(currentFlowId);
  const [isDragging, setIsDragging] = useState(false);

  const { dragOver, dragEnter, dragLeave } = useDragAndDrop(setIsDragging);

  const onDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
      e.dataTransfer.clearData();
    }
    setIsDragging(false);
  };

  const flowRunningSkeletonMemo = useMemo(() => <FlowRunningSqueleton />, []);

  return (
    <div
      className="flex h-full w-full flex-col rounded-md"
      onDragOver={dragOver}
      onDragEnter={dragEnter}
      onDragLeave={dragLeave}
      onDrop={onDrop}
    >
      <div ref={messagesRef} className="chat-message-div">
        {chatHistory &&
          (lockChat || chatHistory?.length > 0 ? (
            <>
              {chatHistory?.map((chat, index) => (
                <MemoizedChatMessage
                  lockChat={lockChat}
                  chat={chat}
                  lastMessage={chatHistory.length - 1 === index}
                  key={`${chat.id}-${index}`}
                  closeChat={closeChat}
                />
              ))}
            </>
          ) : (
            <div className="flex h-full w-full flex-col items-center justify-center">
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
        <div
          className={
            displayLoadingMessage
              ? "w-full max-w-[768px] py-4 word-break-break-word md:w-5/6"
              : ""
          }
          ref={ref}
        >
          {displayLoadingMessage &&
            !(chatHistory?.[chatHistory.length - 1]?.category === "error") &&
            flowRunningSkeletonMemo}
        </div>
      </div>
      <div className="m-auto w-full max-w-[768px] md:w-5/6">
        <ChatInput
          noInput={!inputTypes.includes("ChatInput")}
          lockChat={lockChat}
          sendMessage={({ repeat, files }) => {
            sendMessage({ repeat, files });
            track("Playground Message Sent");
          }}
          inputRef={ref}
          files={files}
          setFiles={setFiles}
          isDragging={isDragging}
        />
      </div>
    </div>
  );
}
