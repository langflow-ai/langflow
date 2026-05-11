import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useRef } from "react";
import { useChatFileUpload } from "@/shared/hooks/use-chat-file-upload";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { ChatInputType, FilePreviewType } from "@/types/components";
import InputWrapper from "./components/input-wrapper";
import NoInputView from "./components/no-input";
import { useAudioRecording } from "./hooks/use-audio-recording";

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
  const stopBuilding = useFlowStore((state) => state.stopBuilding);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const chatValue = useUtilityStore((state) => state.chatValueStore);
  const setChatValueStore = useUtilityStore((state) => state.setChatValueStore);
  const setAwaitingBotResponse = useUtilityStore(
    (state) => state.setAwaitingBotResponse,
  );

  const inputRef = useRef<HTMLTextAreaElement>(null!);
  const { handleFileChange } = useChatFileUpload({
    currentFlowId,
    setFiles,
    playgroundPage: true,
  });

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

  useEffect(() => {
    document.addEventListener("paste", handleFileChange);
    return () => {
      document.removeEventListener("paste", handleFileChange);
    };
  }, [handleFileChange]);

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
      setAwaitingBotResponse?.(false);
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
