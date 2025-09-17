import { useEffect, useRef, useState } from "react";
import { StickToBottom } from "use-stick-to-bottom";
import { v5 as uuidv5 } from "uuid";
import { useGetMessagesQuery } from "@/controllers/API/queries/messages";
import CustomChatInput from "@/customization/components/custom-chat-input";
import { ENABLE_IMAGE_ON_PLAYGROUND } from "@/customization/feature-flags";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { useVoiceStore } from "@/stores/voiceStore";
import type { Message } from "@/types/messages";
import { cn } from "@/utils/utils";
import useTabVisibility from "../../../../../shared/hooks/use-tab-visibility";
import useFlowStore from "../../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import { BotMessage } from "./botMessage/bot-message";
import useDragAndDrop from "./chatInput/hooks/use-drag-and-drop";
import { useFileHandler } from "./chatInput/hooks/use-file-handler";
import { ErrorMessage } from "./errorMessage/error-message";
import { UserMessage } from "./userMessage/user-message";

export default function ChatView(): JSX.Element {
  const inputs = useFlowStore((state) => state.inputs);
  const clientId = useUtilityStore((state) => state.clientId);
  const realFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const playgroundPage = usePlaygroundStore((state) => state.isPlayground);
  const visibleSession = usePlaygroundStore((state) => state.selectedSession);
  const currentFlowId = playgroundPage
    ? uuidv5(`${clientId}_${realFlowId}`, uuidv5.DNS)
    : realFlowId;

  const nodes = useFlowStore((state) => state.nodes);
  const chatInput = inputs.find((input) => input.type === "ChatInput");
  const chatInputNode = nodes.find((node) => node.id === chatInput?.id);

  const isBuilding = useFlowStore((state) => state.isBuilding);

  const inputTypes = inputs.map((obj) => obj.type);
  const setChatValueStore = useUtilityStore((state) => state.setChatValueStore);
  const isTabHidden = useTabVisibility();

  const { data: messages = [] } = useGetMessagesQuery({
    id: currentFlowId,
    session_id: visibleSession,
  });

  //build chat history
  useEffect(() => {
    if (messages.length === 0 && !isBuilding && chatInputNode && isTabHidden) {
      setChatValueStore(
        chatInputNode.data.node.template["input_value"].value ?? "",
      );
    }
  }, [messages, isBuilding, chatInputNode, isTabHidden, setChatValueStore]);

  const ref = useRef<HTMLDivElement | null>(null);

  function updateChat(chat: Message, message: string) {
    chat.text = message;
  }

  const { files, setFiles, handleFiles } = useFileHandler(realFlowId);
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

  const isVoiceAssistantActive = useVoiceStore(
    (state) => state.isVoiceAssistantActive,
  );

  console.log("messages", messages);

  return (
    <StickToBottom
      className={cn(
        "flex h-full flex-1 flex-col rounded-md",
        !isVoiceAssistantActive && "pointer-events-auto",
      )}
      onDragOver={dragOver}
      onDragEnter={dragEnter}
      onDragLeave={dragLeave}
      onDrop={onDrop}
      resize="smooth"
      initial="instant"
      mass={1}
    >
      <StickToBottom.Content className="flex flex-col min-h-full overflow-x-hidden p-4">
        <div className="flex flex-col place-self-center max-w-[768px] w-full">
          {messages?.map((chat, index) =>
            chat.category === "error" ? (
              <ErrorMessage chat={chat} key={`${chat.id}-${index}`} />
            ) : chat.sender === "User" ? (
              <UserMessage
                chat={chat}
                lastMessage={messages.length - 1 === index}
                key={`${chat.id}-${index}`}
                updateChat={updateChat}
                playgroundPage={playgroundPage}
              />
            ) : (
              <BotMessage
                chat={chat}
                lastMessage={messages.length - 1 === index}
                key={`${chat.id}-${index}`}
                updateChat={updateChat}
                playgroundPage={playgroundPage}
              />
            ),
          )}
        </div>
      </StickToBottom.Content>

      <div className="m-auto w-full max-w-[768px] p-4">
        <CustomChatInput
          playgroundPage={!!playgroundPage}
          noInput={!inputTypes.includes("ChatInput")}
          inputRef={ref}
          files={files}
          setFiles={setFiles}
          isDragging={isDragging}
        />
      </div>
    </StickToBottom>
  );
}
