import ChatInput from "@/components/core/playgroundComponent/components/chatView/chatInput/chat-input";
import type { ChatInputType } from "@/types/components";

export const CustomChatInput = ({
  noInput,
  files,
  setFiles,
  isDragging,
  playgroundPage,
}: ChatInputType) => {
  return (
    <ChatInput
      noInput={noInput}
      files={files}
      setFiles={setFiles}
      isDragging={isDragging}
      playgroundPage={playgroundPage}
    />
  );
};

export default CustomChatInput;
