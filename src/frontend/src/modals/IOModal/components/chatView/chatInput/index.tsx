import { usePostUploadFile } from "@/controllers/API/queries/files/use-post-upload-file";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";
import useAlertStore from "@/stores/alertStore";
import { useEffect, useRef, useState } from "react";
import ShortUniqueId from "short-unique-id";
import {
  ALLOWED_IMAGE_INPUT_EXTENSIONS,
  CHAT_INPUT_PLACEHOLDER,
  CHAT_INPUT_PLACEHOLDER_SEND,
  FS_ERROR_TEXT,
  SN_ERROR_TEXT,
} from "../../../../../constants/constants";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import {
  ChatInputType,
  FilePreviewType,
} from "../../../../../types/components";
import FilePreview from "../filePreviewChat";
import ButtonSendWrapper from "./components/buttonSendWrapper";
import TextAreaWrapper from "./components/textAreaWrapper";
import UploadFileButton from "./components/uploadFileButton";
import { getClassNamesFilePreview } from "./helpers/get-class-file-preview";
import useAutoResizeTextArea from "./hooks/use-auto-resize-text-area";
import useFocusOnUnlock from "./hooks/use-focus-unlock";
export default function ChatInput({
  lockChat,
  chatValue,
  sendMessage,
  setChatValue,
  inputRef,
  noInput,
  files,
  setFiles,
  isDragging,
}: ChatInputType): JSX.Element {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const [inputFocus, setInputFocus] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { validateFileSize } = useFileSizeValidator(setErrorData);

  useFocusOnUnlock(lockChat, inputRef);
  useAutoResizeTextArea(chatValue, inputRef);

  const { mutate } = usePostUploadFile();

  const handleFileChange = async (
    event: React.ChangeEvent<HTMLInputElement> | ClipboardEvent,
  ) => {
    let file: File | null = null;

    if ("clipboardData" in event) {
      const items = event.clipboardData?.items;
      if (items) {
        for (let i = 0; i < items.length; i++) {
          const blob = items[i].getAsFile();
          if (blob) {
            file = blob;
            break;
          }
        }
      }
    } else {
      const fileInput = event.target as HTMLInputElement;
      file = fileInput.files?.[0] ?? null;
    }
    if (file) {
      const fileExtension = file.name.split(".").pop()?.toLowerCase();

      if (!validateFileSize(file)) {
        return;
      }

      if (
        !fileExtension ||
        !ALLOWED_IMAGE_INPUT_EXTENSIONS.includes(fileExtension)
      ) {
        setErrorData({
          title: "Error uploading file",
          list: [FS_ERROR_TEXT, SN_ERROR_TEXT],
        });
        return;
      }

      const uid = new ShortUniqueId();
      const id = uid.randomUUID(10);

      const type = file.type.split("/")[0];

      setFiles((prevFiles) => [
        ...prevFiles,
        { file, loading: true, error: false, id, type },
      ]);

      mutate(
        { file, id: currentFlowId },
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

    if ("target" in event && event.target instanceof HTMLInputElement) {
      event.target.value = "";
    }
  };

  useEffect(() => {
    document.addEventListener("paste", handleFileChange);
    return () => {
      document.removeEventListener("paste", handleFileChange);
    };
  }, [handleFileChange, currentFlowId, lockChat]);

  const send = () => {
    sendMessage({
      repeat: 1,
      files: files.map((file) => file.path ?? "").filter((file) => file !== ""),
    });
    setFiles([]);
  };

  const checkSendingOk = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    return (
      event.key === "Enter" &&
      !lockChat &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    );
  };

  const classNameFilePreview = getClassNamesFilePreview(inputFocus);

  const handleButtonClick = () => {
    fileInputRef.current!.click();
  };

  return (
    <div className="flex w-full flex-col-reverse">
      <div className="w-full">
        <TextAreaWrapper
          checkSendingOk={checkSendingOk}
          send={send}
          lockChat={lockChat}
          noInput={noInput}
          chatValue={chatValue}
          setChatValue={setChatValue}
          CHAT_INPUT_PLACEHOLDER={CHAT_INPUT_PLACEHOLDER}
          CHAT_INPUT_PLACEHOLDER_SEND={CHAT_INPUT_PLACEHOLDER_SEND}
          inputRef={inputRef}
          setInputFocus={setInputFocus}
          files={files}
          isDragging={isDragging}
        />
        <div className="form-modal-send-icon-position">
          <ButtonSendWrapper
            send={send}
            lockChat={lockChat}
            noInput={noInput}
            chatValue={chatValue}
            files={files}
          />
        </div>

        <div
          className={`absolute bottom-2 left-4 ${
            lockChat ? "cursor-not-allowed" : ""
          }`}
        >
          <UploadFileButton
            lockChat={lockChat}
            fileInputRef={fileInputRef}
            handleFileChange={handleFileChange}
            handleButtonClick={handleButtonClick}
          />
        </div>
      </div>
      {files.length > 0 && (
        <div className={classNameFilePreview}>
          {files.map((file) => (
            <FilePreview
              error={file.error}
              file={file.file}
              loading={file.loading}
              key={file.id}
              onDelete={() => {
                setFiles((prev: FilePreviewType[]) =>
                  prev.filter((f) => f.id !== file.id),
                );
                // TODO: delete file on backend
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
