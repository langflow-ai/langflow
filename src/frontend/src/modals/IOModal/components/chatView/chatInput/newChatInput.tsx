import { Button } from "@/components/ui/button";
import Loading from "@/components/ui/loading";
import { usePostUploadFile } from "@/controllers/API/queries/files/use-post-upload-file";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
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
import FilePreview from "../filePreviewChat/newFilePreview";
import ButtonSendWrapper from "./components/buttonSendWrapper/newButtonSendWrapper";
import TextAreaWrapper from "./components/textAreaWrapper/newTextAreaWrapper";
import UploadFileButton from "./components/uploadFileButton/newUploadFileButton";
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
  const stopBuilding = useFlowStore((state) => state.stopBuilding);

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

  const classNameFilePreview = `flex w-full items-center gap-2 py-2 overflow-auto custom-scroll`;

  const handleButtonClick = () => {
    fileInputRef.current!.click();
  };

  const handleDeleteFile = (file: FilePreviewType) => {
    setFiles((prev: FilePreviewType[]) => prev.filter((f) => f.id !== file.id));
    // TODO: delete file on backend
  };

  if (noInput) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center">
        <div className="flex w-full flex-col items-center justify-center gap-3 rounded-md border border-input bg-muted p-2 py-4">
          {!lockChat ? (
            <Button
              data-testid="button-send"
              className="font-semibold"
              onClick={() => {
                sendMessage({
                  repeat: 1,
                });
              }}
            >
              Run Flow
            </Button>
          ) : (
            <Button
              onClick={stopBuilding}
              data-testid="button-stop"
              unstyled
              className="form-modal-send-button cursor-pointer bg-muted text-foreground hover:bg-secondary-hover dark:hover:bg-input"
            >
              <div className="flex items-center gap-2 rounded-md text-[14px] font-medium">
                Stop
                <Loading className="h-[16px] w-[16px]" />
              </div>
            </Button>
          )}

          <p className="text-muted-foreground">
            Add a{" "}
            <a
              className="underline underline-offset-4"
              target="_blank"
              href="https://docs.langflow.org/components-io#chat-input"
            >
              Chat Input
            </a>{" "}
            component to your flow to send messages.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex w-full flex-col-reverse">
      <div className="flex w-full flex-col rounded-md border border-input p-4 hover:border-muted-foreground focus:border-[1.75px] has-[:focus]:border-primary">
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
        <div className={classNameFilePreview}>
          {files.map((file) => (
            <FilePreview
              error={file.error}
              file={file.file}
              loading={file.loading}
              key={file.id}
              onDelete={() => {
                handleDeleteFile(file);
              }}
            />
          ))}
        </div>
        <div className="flex w-full items-end justify-between">
          <div className={lockChat ? "cursor-not-allowed" : ""}>
            <UploadFileButton
              lockChat={lockChat}
              fileInputRef={fileInputRef}
              handleFileChange={handleFileChange}
              handleButtonClick={handleButtonClick}
            />
          </div>
          <div className="">
            <ButtonSendWrapper
              send={send}
              lockChat={lockChat}
              noInput={noInput}
              chatValue={chatValue}
              files={files}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
