import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useRef } from "react";
import ShortUniqueId from "short-unique-id";
import {
  ALLOWED_IMAGE_INPUT_EXTENSIONS,
  FS_ERROR_TEXT,
  SN_ERROR_TEXT,
} from "@/constants/constants";
import { usePostUploadFile } from "@/controllers/API/queries/files/use-post-upload-file";
import useFileSizeValidator from "@/shared/hooks/use-file-size-validator";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { ChatInputType, FilePreviewType } from "@/types/components";
import InputWrapper from "./components/input-wrapper";
import NoInputView from "./components/no-input";
import { useAudioRecording } from "./hooks/use-audio-recording";
import useAutoResizeTextArea from "./hooks/use-auto-resize-text-area";

interface ChatInputProps
  extends Omit<ChatInputType, "sendMessage" | "inputRef"> {
  sendMessage: (params: {
    inputValue: string;
    files: string[];
  }) => Promise<void>;
}

export default function ChatInput({
  noInput,
  files,
  setFiles,
  isDragging,
  sendMessage,
}: ChatInputProps): JSX.Element {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { validateFileSize } = useFileSizeValidator();
  const stopBuilding = useFlowStore((state) => state.stopBuilding);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const chatValue = useUtilityStore((state) => state.chatValueStore);
  const setChatValueStore = useUtilityStore((state) => state.setChatValueStore);
  const setAwaitingBotResponse = useUtilityStore(
    (state) => state.setAwaitingBotResponse,
  );

  const inputRef = useRef<HTMLTextAreaElement>(null);

  const { mutate } = usePostUploadFile();

  // Audio transcription handler - appends transcribed text to the chat input
  const handleTranscriptionComplete = useCallback(
    (transcribedText: string) => {
      // Append to existing chat value with a space if there's existing text
      const currentValue = useUtilityStore.getState().chatValueStore;
      setChatValueStore(
        currentValue ? `${currentValue} ${transcribedText}` : transcribedText,
      );
      // Focus the input after transcription
      inputRef.current?.focus();
    },
    [setChatValueStore],
  );

  const handleAudioError = useCallback(
    (error: string) => {
      setErrorData({
        title: "Voice Input Error",
        list: [error],
      });
    },
    [setErrorData],
  );

  const {
    state: audioRecordingState,
    startRecording,
    stopRecording,
    isSupported: isAudioSupported,
  } = useAudioRecording({
    onTranscriptionComplete: handleTranscriptionComplete,
    onError: handleAudioError,
  });

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

      try {
        validateFileSize(file);
      } catch (e) {
        if (e instanceof Error) {
          setErrorData({
            title: e.message,
          });
        }
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
              const updatedIndex = newFiles.findIndex((f) => f.id === id);
              newFiles[updatedIndex].loading = false;
              newFiles[updatedIndex].path = data.file_path;
              return newFiles;
            });
          },
          onError: (error) => {
            setFiles((prev) => {
              const newFiles = [...prev];
              const updatedIndex = newFiles.findIndex((f) => f.id === id);
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
  }, [currentFlowId, isBuilding]);

  const send = async () => {
    // Indicate we are awaiting a bot response so typing animation can start
    setAwaitingBotResponse?.(true);
    const storedChatValue = chatValue;
    const filesToSend = files
      .map((file) => file.path ?? "")
      .filter((file) => file !== "");
    const storedFiles = [...files];
    setFiles([]);
    setChatValueStore("");
    try {
      await sendMessage({
        inputValue: storedChatValue,
        files: filesToSend,
      });
    } catch (_error) {
      setChatValueStore(storedChatValue);
      setFiles(storedFiles);
    }
  };

  const checkSendingOk = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    return (
      event.key === "Enter" &&
      !isBuilding &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    );
  };

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  const handleDeleteFile = (file: FilePreviewType) => {
    setFiles((prev: FilePreviewType[]) => prev.filter((f) => f.id !== file.id));
  };

  if (noInput) {
    return (
      <NoInputView
        isBuilding={isBuilding}
        sendMessage={send}
        stopBuilding={stopBuilding}
      />
    );
  }

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key="input-wrapper"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
      >
        <InputWrapper
          isBuilding={isBuilding}
          checkSendingOk={checkSendingOk}
          send={send}
          noInput={noInput}
          chatValue={chatValue}
          inputRef={inputRef}
          files={files}
          isDragging={isDragging}
          handleDeleteFile={handleDeleteFile}
          fileInputRef={fileInputRef}
          handleFileChange={handleFileChange}
          handleButtonClick={handleButtonClick}
          audioRecordingState={audioRecordingState}
          onStartRecording={startRecording}
          onStopRecording={stopRecording}
          isAudioSupported={isAudioSupported}
        />
      </motion.div>
    </AnimatePresence>
  );
}
