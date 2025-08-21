import ChatInput from "@/components/core/playgroundComponent/components/chatView/chatInput/chat-input";
import type { ChatInputType } from "@/types/components";

export const CustomChatInput = ({
  inputRef,
  noInput,
  files,
  setFiles,
  isDragging,
  playgroundPage,
}: ChatInputType) => {
  return (
    <ChatInput
      inputRef={inputRef}
      noInput={noInput}
      files={files}
      setFiles={setFiles}
      isDragging={isDragging}
      playgroundPage={playgroundPage}
    />
  );
};

export default CustomChatInput;
