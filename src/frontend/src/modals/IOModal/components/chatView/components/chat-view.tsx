import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import { TextEffectPerChar } from "@/components/ui/textAnimation";
import { ENABLE_IMAGE_ON_PLAYGROUND } from "@/customization/feature-flags";
import { track } from "@/customization/utils/analytics";
import { useMessagesStore } from "@/stores/messagesStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { useVoiceStore } from "@/stores/voiceStore";
import { cn } from "@/utils/utils";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import { v5 as uuidv5 } from "uuid";
import useTabVisibility from "../../../../../shared/hooks/use-tab-visibility";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import useFlowStore from "../../../../../stores/flowStore";
import { ChatMessageType } from "../../../../../types/chat";
import { chatViewProps } from "../../../../../types/components";
import FlowRunningSqueleton from "../../flow-running-squeleton";
import ChatInput from "../chatInput/chat-input";
import useDragAndDrop from "../chatInput/hooks/use-drag-and-drop";
import { useFileHandler } from "../chatInput/hooks/use-file-handler";
import ChatMessage from "../chatMessage/chat-message";

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

export default function ChatView({
  sendMessage,
  visibleSession,
  focusChat,
  closeChat,
  playgroundPage,
  sidebarOpen,
}: chatViewProps): JSX.Element {
  const flowPool = useFlowStore((state) => state.flowPool);
  const inputs = useFlowStore((state) => state.inputs);
  const clientId = useUtilityStore((state) => state.clientId);
  let realFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const currentFlowId = playgroundPage
    ? uuidv5(`${clientId}_${realFlowId}`, uuidv5.DNS)
    : realFlowId;
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessageType[] | undefined>(
    undefined,
  );
  const messages = useMessagesStore((state) => state.messages);
  const nodes = useFlowStore((state) => state.nodes);
  const chatInput = inputs.find((input) => input.type === "ChatInput");
  const chatInputNode = nodes.find((node) => node.id === chatInput?.id);
  const displayLoadingMessage = useMessagesStore(
    (state) => state.displayLoadingMessage,
  );

  const isBuilding = useFlowStore((state) => state.isBuilding);

  const inputTypes = inputs.map((obj) => obj.type);
  const updateFlowPool = useFlowStore((state) => state.updateFlowPool);
  const setChatValueStore = useUtilityStore((state) => state.setChatValueStore);
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

    if (messages.length === 0 && !isBuilding && chatInputNode && isTabHidden) {
      setChatValueStore(
        chatInputNode.data.node.template["input_value"].value ?? "",
      );
    }

    setChatHistory(finalChatHistory);
  }, [messages, visibleSession]);

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

  function updateChat(
    chat: ChatMessageType,
    message: string,
    stream_url?: string,
  ) {
    chat.message = message;
    if (chat.componentId)
      updateFlowPool(chat.componentId, {
        message,
        sender_name: chat.sender_name ?? "Bot",
        sender: chat.isSend ? "User" : "Machine",
      });
  }

  const { files, setFiles, handleFiles } = useFileHandler(currentFlowId);
  const [isDragging, setIsDragging] = useState(false);

  const { dragOver, dragEnter, dragLeave } = useDragAndDrop(setIsDragging);

  const onDrop = (e) => {
    if (!ENABLE_IMAGE_ON_PLAYGROUND) {
      e.stopPropagation();
      return;
    }
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
      e.dataTransfer.clearData();
    }
    setIsDragging(false);
  };

  const flowRunningSkeletonMemo = useMemo(() => <FlowRunningSqueleton />, []);
  const isVoiceAssistantActive = useVoiceStore(
    (state) => state.isVoiceAssistantActive,
  );

  return (
    <div
      className={cn(
        "flex h-full w-full flex-col rounded-md",
        visibleSession ? "h-[95%]" : "h-full",
        sidebarOpen &&
          !isVoiceAssistantActive &&
          "pointer-events-none blur-sm lg:pointer-events-auto lg:blur-0",
      )}
      onDragOver={dragOver}
      onDragEnter={dragEnter}
      onDragLeave={dragLeave}
      onDrop={onDrop}
    >
      <div ref={messagesRef} className="chat-message-div">
        {chatHistory &&
          (isBuilding || chatHistory?.length > 0 ? (
            <>
              {chatHistory?.map((chat, index) => (
                <MemoizedChatMessage
                  chat={chat}
                  lastMessage={chatHistory.length - 1 === index}
                  key={`${chat.id}-${index}`}
                  updateChat={updateChat}
                  closeChat={closeChat}
                  playgroundPage={playgroundPage}
                  sidebarOpen={sidebarOpen}
                />
              ))}
            </>
          ) : (
            <div className="flex h-full w-full flex-col items-center justify-center">
              <LangflowLogo className="mb-2 h-10 w-10" />
              <div className="mx-auto w-full text-center text-2xl font-semibold text-primary">
                <TextEffectPerChar text="Type to start the flow" />
              </div>
            </div>
          ))}
        {isBuilding && displayLoadingMessage && flowRunningSkeletonMemo}
      </div>
      {chatInput && ( // Only show chat input if there is a chat input node
        <div className="w-full pt-2">
          <ChatInput
            isDragging={isDragging}
            files={files}
            setFiles={setFiles}
            sendMessage={sendMessage}
            inputRef={ref}
            noInput={!chatInput}
            playgroundPage={playgroundPage}
          />
        </div>
      )}
    </div>
  );
}
