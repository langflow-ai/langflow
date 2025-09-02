import { memo, useEffect, useMemo, useRef, useState } from "react";
import { StickToBottom } from "use-stick-to-bottom";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import { TextEffectPerChar } from "@/components/ui/textAnimation";
import CustomChatInput from "@/customization/components/custom-chat-input";
import { ENABLE_IMAGE_ON_PLAYGROUND } from "@/customization/feature-flags";
import useCustomUseFileHandler from "@/customization/hooks/use-custom-use-file-handler";
import { track } from "@/customization/utils/analytics";
import { useGetFlowId } from "@/modals/IOModal/hooks/useGetFlowId";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useMessagesStore } from "@/stores/messagesStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { useVoiceStore } from "@/stores/voiceStore";
import { cn } from "@/utils/utils";
import useTabVisibility from "../../../../../shared/hooks/use-tab-visibility";
import useFlowStore from "../../../../../stores/flowStore";
import type { ChatMessageType } from "../../../../../types/chat";
import type { chatViewProps } from "../../../../../types/components";
import FlowRunningSqueleton from "../../flow-running-squeleton";
import useDragAndDrop from "../chatInput/hooks/use-drag-and-drop";
import ChatMessage from "../chatMessage/chat-message";
import sortSenderMessages from "../helpers/sort-sender-messages";

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
  const inputs = useFlowStore((state) => state.inputs);
  const realFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const currentFlowId = useGetFlowId();
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

    const finalChatHistory = [...messagesFromMessagesStore].sort(
      sortSenderMessages,
    );

    if (messages.length === 0 && !isBuilding && chatInputNode && isTabHidden) {
      setChatValueStore(
        chatInputNode.data.node.template["input_value"].value ?? "",
      );
    }

    setChatHistory(finalChatHistory);
  }, [messages, visibleSession]);

  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (ref.current && focusChat) {
      ref.current.focus();
    }
    // trigger focus on chat when new session is set
  }, [focusChat]);

  function updateChat(chat: ChatMessageType, message: string) {
    chat.message = message;
    if (chat.componentId)
      updateFlowPool(chat.componentId, {
        message,
        sender_name: chat.sender_name ?? "Bot",
        sender: chat.isSend ? "User" : "Machine",
      });
  }

  const { files, setFiles, handleFiles } = useCustomUseFileHandler(realFlowId);
  const [isDragging, setIsDragging] = useState(false);

  const { dragOver, dragEnter, dragLeave } = useDragAndDrop(
    setIsDragging,
    !!playgroundPage,
  );

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    if (!ENABLE_IMAGE_ON_PLAYGROUND && playgroundPage) {
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
    <StickToBottom
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
      resize="smooth"
      initial="instant"
      mass={1}
    >
      <StickToBottom.Content className="flex flex-col min-h-full">
        <div className="flex flex-col flex-grow place-self-center w-5/6 max-w-[768px]">
          {chatHistory &&
            (isBuilding || chatHistory?.length > 0 ? (
              chatHistory?.map((chat, index) => (
                <MemoizedChatMessage
                  chat={chat}
                  lastMessage={chatHistory.length - 1 === index}
                  key={`${chat.id}-${index}`}
                  updateChat={updateChat}
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
      </StickToBottom.Content>

      <div className="m-auto w-full max-w-[768px] md:w-5/6">
        <CustomChatInput
          playgroundPage={!!playgroundPage}
          noInput={!inputTypes.includes("ChatInput")}
          sendMessage={async ({ repeat, files }) => {
            await sendMessage({ repeat, files });
            track("Playground Message Sent");
          }}
          inputRef={ref}
          files={files}
          setFiles={setFiles}
          isDragging={isDragging}
        />
      </div>
    </StickToBottom>
  );
}
