import { INVALID_FILE_SIZE_ALERT } from "@/constants/alerts_constants";
import { useDeleteBuilds } from "@/controllers/API/queries/_builds";
import { usePostUploadFile } from "@/controllers/API/queries/files/use-post-upload-file";
import { track } from "@/customization/utils/analytics";
import { useMessagesStore } from "@/stores/messagesStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { useEffect, useRef, useState } from "react";
import ShortUniqueId from "short-unique-id";
import IconComponent from "../../../../components/genericIconComponent";
import {
  ALLOWED_IMAGE_INPUT_EXTENSIONS,
  CHAT_FIRST_INITIAL_TEXT,
  CHAT_SECOND_INITIAL_TEXT,
  FS_ERROR_TEXT,
  SN_ERROR_TEXT,
} from "../../../../constants/constants";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { ChatMessageType, PlaygroundEvent } from "../../../../types/chat";
import { FilePreviewType, chatViewProps } from "../../../../types/components";
import ChatInput from "./chatInput";
import useDragAndDrop from "./chatInput/hooks/use-drag-and-drop";
import ChatMessage from "./chatMessage";

export default function ChatView({
  sendMessage,
  chatValue,
  setChatValue,
  lockChat,
  setLockChat,
  visibleSession,
  focusChat,
}: chatViewProps): JSX.Element {
  const { flowPool, outputs, inputs, CleanFlowPool } = useFlowStore();
  const { setErrorData } = useAlertStore();
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessageType[]>([]);
  const messages = useMessagesStore((state) => state.messages);

  const inputTypes = inputs.map((obj) => obj.type);
  const updateFlowPool = useFlowStore((state) => state.updateFlowPool);
  const [id, setId] = useState<string>("");
  const { mutate: mutateDeleteFlowPool } = useDeleteBuilds();
  const maxFileSizeUpload = useUtilityStore((state) => state.maxFileSizeUpload);

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

  function clearChat(): void {
    setChatHistory([]);

    mutateDeleteFlowPool(
      { flowId: currentFlowId },
      {
        onSuccess: () => {
          CleanFlowPool();
        },
      },
    );
    //TODO tell backend to clear chat session
    if (lockChat) setLockChat(false);
  }

  function handleSelectChange(event: string): void {
    switch (event) {
      case "builds":
        clearChat();
        break;
      case "buildsNSession":
        console.log("delete build and session");
        break;
    }
  }

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
  const [files, setFiles] = useState<FilePreviewType[]>([]);
  const [isDragging, setIsDragging] = useState(false);

  const { dragOver, dragEnter, dragLeave } = useDragAndDrop(setIsDragging);

  const onDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files, setFiles, currentFlowId, setErrorData);
      e.dataTransfer.clearData();
    }
    setIsDragging(false);
  };

  const { mutate } = usePostUploadFile();

  const handleFiles = (files, setFiles, currentFlowId, setErrorData) => {
    if (files) {
      const file = files?.[0];
      const fileExtension = file.name.split(".").pop()?.toLowerCase();
      if (file.size > maxFileSizeUpload) {
        setErrorData({
          title: INVALID_FILE_SIZE_ALERT(maxFileSizeUpload / 1024 / 1024),
        });
        return;
      }

      if (
        !fileExtension ||
        !ALLOWED_IMAGE_INPUT_EXTENSIONS.includes(fileExtension)
      ) {
        console.log("Error uploading file");
        setErrorData({
          title: "Error uploading file",
          list: [FS_ERROR_TEXT, SN_ERROR_TEXT],
        });
        return;
      }
      const uid = new ShortUniqueId();
      const id = uid.randomUUID(3);
      setId(id);

      const type = files[0].type.split("/")[0];
      const blob = files[0];

      setFiles((prevFiles) => [
        ...prevFiles,
        { file: blob, loading: true, error: false, id, type },
      ]);

      mutate(
        { file: blob, id: currentFlowId },
        {
          onSuccess: (data) => {
            setFiles((prev) => {
              const newFiles = [...prev];
              const updatedIndex = newFiles.findIndex((file) => file.id === id);
              newFiles[updatedIndex].loading = false;
              newFiles[updatedIndex].path = data.file_path;
              return newFiles;
            });
          },
          onError: (error) => {
            setFiles((prev) => {
              const newFiles = [...prev];
              const updatedIndex = newFiles.findIndex((file) => file.id === id);
              newFiles[updatedIndex].loading = false;
              newFiles[updatedIndex].error = true;
              return newFiles;
            });
            setErrorData({
              title: "Error uploading file",
              list: [error.response?.data?.detail],
            });
          },
        },
      );
    }
  };

  const handlePlaygroundEvent = (event: PlaygroundEvent) => {
    switch (event.event_type) {
      case "message":
        setChatHistory((prev) => [
          ...prev,
          {
            isSend: event.sender_name === "User",
            message: event.text || "",
            sender_name: event.sender_name,
            files: event.files,
            id: event.id || "",
            timestamp: event.timestamp || "",
            content_blocks: event.content_blocks || undefined,
            background_color: event.background_color || "",
            text_color: event.text_color || "",
          },
        ]);
        break;
      case "error":
        // Handle error event (e.g., display error message)
        setErrorData({
          title: "Error",
          list: event.text ? [event.text] : [],
        });
        break;
      case "warning":
        // Handle warning event
        break;
      case "info":
        // Handle info event
        break;
      case "token":
        // Update the last message with the new token
        setChatHistory((prev) => {
          const newHistory = [...prev];
          const lastMessage = newHistory[newHistory.length - 1];
          if (lastMessage && event.token) {
            lastMessage.message += event.token;
          }
          return newHistory;
        });
        break;
    }
  };

  // Use this function in your streaming logic
  const handleStreamedEvent = (event: any) => {
    const playgroundEvent = event.data as PlaygroundEvent;
    handlePlaygroundEvent(playgroundEvent);
  };

  return (
    <div
      className="eraser-column-arrangement"
      onDragOver={dragOver}
      onDragEnter={dragEnter}
      onDragLeave={dragLeave}
      onDrop={onDrop}
    >
      <div className="eraser-size">
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
              />
            ))
          ) : (
            <div className="chat-alert-box">
              <span>
                👋 <span className="langflow-chat-span">Langflow Chat</span>
              </span>
              <br />
              <div className="langflow-chat-desc">
                <span className="langflow-chat-desc-span">
                  {CHAT_FIRST_INITIAL_TEXT}{" "}
                  <span>
                    <IconComponent
                      name="MessageSquareMore"
                      className="mx-1 inline h-5 w-5 animate-bounce"
                    />
                  </span>{" "}
                  {CHAT_SECOND_INITIAL_TEXT}
                </span>
              </div>
            </div>
          )}
          <div ref={ref}></div>
        </div>
        <div className="langflow-chat-input-div">
          <div className="langflow-chat-input">
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
      </div>
    </div>
  );
}
