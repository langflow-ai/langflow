import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { useStickToBottomContext } from "use-stick-to-bottom";
import { useChatFileUpload } from "@/shared/hooks/use-chat-file-upload";
import useFlowStore from "@/stores/flowStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { useVoiceStore } from "@/stores/voiceStore";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import type {
  ChatInputType,
  FilePreviewType,
} from "../../../../../types/components";
import InputWrapper from "./components/input-wrapper";
import NoInputView from "./components/no-input";
import { VoiceAssistant } from "./components/voice-assistant/voice-assistant";
import useAutoResizeTextArea from "./hooks/use-auto-resize-text-area";
import useFocusOnUnlock from "./hooks/use-focus-unlock";

export default function ChatInput({
  sendMessage,
  inputRef,
  noInput,
  files,
  setFiles,
  isDragging,
  playgroundPage,
}: ChatInputType): JSX.Element {
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const stopBuilding = useFlowStore((state) => state.stopBuilding);
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const chatValue = useUtilityStore((state) => state.chatValueStore);

  const { scrollToBottom } = useStickToBottomContext();

  const [showAudioInput, setShowAudioInput] = useState(false);

  const setIsVoiceAssistantActive = useVoiceStore(
    (state) => state.setIsVoiceAssistantActive,
  );

  const newSessionCloseVoiceAssistant = useVoiceStore(
    (state) => state.newSessionCloseVoiceAssistant,
  );

  useEffect(() => {
    if (showAudioInput) {
      setIsVoiceAssistantActive(true);
    }
  }, [showAudioInput]);

  useFocusOnUnlock(isBuilding, inputRef);
  useAutoResizeTextArea(chatValue, inputRef);

  const { handleFileChange: handleFileUploadChange } = useChatFileUpload({
    currentFlowId,
    setFiles,
    playgroundPage: !!playgroundPage,
  });

  useEffect(() => {
    document.addEventListener("paste", handleFileUploadChange);
    return () => {
      document.removeEventListener("paste", handleFileUploadChange);
    };
  }, [handleFileUploadChange, currentFlowId, isBuilding]);

  const setChatValueStore = useUtilityStore((state) => state.setChatValueStore);

  const send = async () => {
    const storedChatValue = chatValue;
    const filesToSend = files
      .map((file) => file.path ?? "")
      .filter((file) => file !== "");
    const storedFiles = [...files];
    setFiles([]);
    try {
      scrollToBottom({
        animation: "smooth",
        duration: 1000,
      });
      await sendMessage({
        repeat: 1,
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
    fileInputRef.current!.click();
  };

  const handleDeleteFile = (file: FilePreviewType) => {
    setFiles((prev: FilePreviewType[]) => prev.filter((f) => f.id !== file.id));
    // TODO: delete file on backend
  };

  if (noInput) {
    return (
      <NoInputView
        isBuilding={isBuilding}
        sendMessage={sendMessage}
        stopBuilding={stopBuilding}
      />
    );
  }

  return (
    <AnimatePresence mode="wait">
      {showAudioInput && !newSessionCloseVoiceAssistant ? (
        <motion.div
          key="voice-assistant"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <VoiceAssistant
            flowId={currentFlowId}
            setShowAudioInput={setShowAudioInput}
          />
        </motion.div>
      ) : (
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
            handleFileChange={handleFileUploadChange}
            handleButtonClick={handleButtonClick}
            setShowAudioInput={setShowAudioInput}
            currentFlowId={currentFlowId}
            playgroundPage={playgroundPage}
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
}
