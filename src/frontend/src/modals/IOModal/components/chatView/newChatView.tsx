import { TextEffectPerChar } from "@/components/ui/textAnimation";
import { TextShimmer } from "@/components/ui/TextShimmer";
import { track } from "@/customization/utils/analytics";
import { useMessagesStore } from "@/stores/messagesStore";
import { useEffect, useRef, useState } from "react";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import useFlowStore from "../../../../stores/flowStore";
import { ChatMessageType } from "../../../../types/chat";
import { chatViewProps } from "../../../../types/components";
import useDragAndDrop from "./chatInput/hooks/use-drag-and-drop";
import { useFileHandler } from "./chatInput/hooks/use-file-handler";
import ChatInput from "./chatInput/newChatInput";
import LogoIcon from "./chatMessage/components/chatLogoIcon";
import ChatMessage from "./chatMessage/newChatMessage";

export default function ChatView({
  sendMessage,
  chatValue,
  setChatValue,
  lockChat,
  setLockChat,
  visibleSession,
  focusChat,
  closeChat,
}: chatViewProps): JSX.Element {
  const { flowPool, inputs, CleanFlowPool } = useFlowStore();
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessageType[]>([]);
  const messages = useMessagesStore((state) => state.messages);

  const inputTypes = inputs.map((obj) => obj.type);
  const updateFlowPool = useFlowStore((state) => state.updateFlowPool);

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

    setChatHistory(finalChatHistory);
  }, [flowPool, messages, visibleSession]);
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
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
      e.dataTransfer.clearData();
    }
    setIsDragging(false);
  };

  return (
    <div
      className="flex h-full w-full flex-col rounded-md"
      onDragOver={dragOver}
      onDragEnter={dragEnter}
      onDragLeave={dragLeave}
      onDrop={onDrop}
    >
      <div ref={messagesRef} className="chat-message-div">
        {chatHistory?.length > 0 ? (
          chatHistory.map((chat, index) => (
            <ChatMessage
              setLockChat={setLockChat}
              lockChat={lockChat}
              chat={chat}
              lastMessage={chatHistory.length - 1 === index ? true : false}
              key={`${chat.id}-${index}`}
              updateChat={updateChat}
              closeChat={closeChat}
            />
          ))
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center">
            <div className="flex flex-col items-center justify-center gap-4 p-8">
              <img
                src="/src/assets/logo.svg"
                alt="Chain logo"
                className="h-[40px] w-[40px] scale-[1.5]"
              />
              <div className="flex flex-col items-center justify-center">
                <h3 className="mt-2 pb-2 text-2xl font-semibold text-primary">
                  New chat
                </h3>
                <p className="text-lg text-muted-foreground">
                  <TextEffectPerChar>
                    Test your flow with a chat prompt
                  </TextEffectPerChar>
                </p>
              </div>
            </div>
          </div>
        )}
        <div
          className={
            lockChat ? "w-5/6 max-w-[768px] py-4 word-break-break-word" : ""
          }
          ref={ref}
        >
          {lockChat &&
            chatHistory.length > 0 &&
            !(chatHistory[chatHistory.length - 1]?.category === "error") && (
              <div className="flex w-full gap-4 rounded-md p-2">
                <LogoIcon />
                <div className="flex items-center">
                  <div>
                    <TextShimmer className="" duration={1}>
                      Flow running...
                    </TextShimmer>
                  </div>
                </div>
              </div>
            )}
        </div>
      </div>
      <div className="m-auto w-5/6 max-w-[768px]">
        <ChatInput
          chatValue={chatValue}
          noInput={!inputTypes.includes("ChatInput")}
          lockChat={lockChat}
          sendMessage={({ repeat, files }) => {
            sendMessage({ repeat, files });
            track("Playground Message Sent");
          }}
          setChatValue={(value) => {
            setChatValue(value);
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
