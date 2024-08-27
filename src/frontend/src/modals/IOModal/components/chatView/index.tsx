import { useDeleteBuilds } from "@/controllers/API/queries/_builds";
import { usePostUploadFile } from "@/controllers/API/queries/files/use-post-upload-file";
import { useEffect, useRef, useState } from "react";
import ShortUniqueId from "short-unique-id";
import IconComponent from "../../../../components/genericIconComponent";
import { Button } from "../../../../components/ui/button";
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
import { VertexBuildTypeAPI } from "../../../../types/api";
import { ChatMessageType } from "../../../../types/chat";
import { FilePreviewType, chatViewProps } from "../../../../types/components";
import { classNames, removeDuplicatesBasedOnAttribute } from "../../../../utils/utils";
import ChatInput from "./chatInput";
import useDragAndDrop from "./chatInput/hooks/use-drag-and-drop";
import ChatMessage from "./chatMessage";
import { useMessagesStore } from "@/stores/messagesStore";

export default function ChatView({
  sendMessage,
  chatValue,
  setChatValue,
  lockChat,
  setLockChat,
}: chatViewProps): JSX.Element {
  const { flowPool, outputs, inputs, CleanFlowPool } = useFlowStore();
  const { setErrorData } = useAlertStore();
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessageType[]>([]);
  const messages = useMessagesStore((state) => state.messages);

  const inputTypes = inputs.map((obj) => obj.type);
  const inputIds = inputs.map((obj) => obj.id);
  const outputIds = outputs.map((obj) => obj.id);
  const updateFlowPool = useFlowStore((state) => state.updateFlowPool);
  const [id, setId] = useState<string>("");
  const { mutate: mutateDeleteFlowPool } = useDeleteBuilds();

  //build chat history
  useEffect(() => {
    const chatOutputResponses: VertexBuildTypeAPI[] = [];
    outputIds.forEach((outputId) => {
      if (outputId.includes("ChatOutput")) {
        if (flowPool[outputId] && flowPool[outputId].length > 0) {
          chatOutputResponses.push(...flowPool[outputId]);
        }
      }
    });
    inputIds.forEach((inputId) => {
      if (inputId.includes("ChatInput")) {
        if (flowPool[inputId] && flowPool[inputId].length > 0) {
          chatOutputResponses.push(...flowPool[inputId]);
        }
      }
    });
    const messagesFromPool: ChatMessageType[] = chatOutputResponses
      .filter(
        (output) =>
          output.data.message!==undefined
      )
      .map((output, index) => {
        try {
          const messageOutput = output.data.message!;
          const { sender, message, sender_name, stream_url, files } = messageOutput

          const is_ai =
            sender === "Machine" || sender === null || sender === undefined;
          return {
            isSend: !is_ai,
            message,
            sender_name,
            stream_url: stream_url,
            files,
            timestamp: output.timestamp,
          };
        } catch (e) {
          console.error(e);
          return {
            isSend: false,
            message: "Error parsing message",
            sender_name: "Error",
            componentId: output.id,
            timestamp: output.timestamp,
          };
        }
      });
    const messagesFromMessagesStore:ChatMessageType[] = messages.filter(message=>message.flow_id===currentFlowId)
    .map((message) => {
      let files = message.files;
      //HANDLE THE "[]" case
      if(typeof files === "string") {
        files = JSON.parse(files);
      }
      return {
        isSend: message.sender === "User",
        message: message.text,
        sender_name: message.sender_name,
        files: files,
        id: message.id,
        timestamp: message.timestamp,
      };
    });
    const finalChatHistory = [...messagesFromMessagesStore].sort((a, b) => {
      return (new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
    })
    // this function will remove duplicates from the chat history based on the timestamp
    setChatHistory(finalChatHistory);

  }, [flowPool,messages]);
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
  }, []);

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
    if(chat.componentId) updateFlowPool(chat.componentId, {
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
          onError: () => {
            setFiles((prev) => {
              const newFiles = [...prev];
              const updatedIndex = newFiles.findIndex((file) => file.id === id);
              newFiles[updatedIndex].loading = false;
              newFiles[updatedIndex].error = true;
              return newFiles;
            });
          },
        },
      );
    }
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
        <div className="eraser-position">
          <Button
            className="flex gap-1"
            unstyled
            disabled={lockChat}
            onClick={() => handleSelectChange("builds")}
          >
            <IconComponent
              name="Eraser"
              className={classNames("h-5 w-5 text-primary")}
              aria-hidden="true"
            />
          </Button>
        </div>
        <div ref={messagesRef} className="chat-message-div">
          {chatHistory?.length > 0 ? (
            chatHistory.map((chat, index) => (
              <ChatMessage
                setLockChat={setLockChat}
                lockChat={lockChat}
                chat={chat}
                lastMessage={chatHistory.length - 1 === index ? true : false}
                key={`${chat.componentId}-${index}`}
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
              sendMessage={({ repeat, files }) =>
                sendMessage({ repeat, files })
              }
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
