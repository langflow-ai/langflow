import { Textarea } from "@/components/ui/textarea";
import { useUtilityStore } from "@/stores/utilityStore";
import type { FilePreviewType } from "@/types/components";
import { cn } from "@/utils/utils";

interface TextAreaWrapperProps {
  checkSendingOk: (event: React.KeyboardEvent<HTMLTextAreaElement>) => boolean;
  send: () => void;
  isBuilding: boolean;
  noInput: boolean;
  chatValue: string;
  inputRef: React.RefObject<HTMLTextAreaElement>;
  files: FilePreviewType[];
  isDragging: boolean;
}

const TextAreaWrapper = ({
  checkSendingOk,
  send,
  isBuilding,
  noInput,
  chatValue,
  inputRef,
  files,
  isDragging,
}: TextAreaWrapperProps) => {
  const getPlaceholderText = (
    isDragging: boolean,
    noInput: boolean,
  ): string => {
    if (isDragging) {
      return "Drop here";
    } else if (noInput) {
      return "No chat input available";
    } else {
      return "Send a message...";
    }
  };

  const fileClass = files.length > 0 ? "!rounded-t-none border-t-0" : "";

  const setChatValueStore = useUtilityStore((state) => state.setChatValueStore);

  return (
    <Textarea
      id="chat-input-textarea"
      name="chat-input"
      data-testid="input-chat-playground"
      onKeyDown={(event) => {
        if (checkSendingOk(event)) {
          event.preventDefault();
          send();
        }
      }}
      rows={1}
      ref={inputRef}
      disabled={isBuilding || noInput}
      style={{
        resize: "none",
        bottom: `${inputRef?.current?.scrollHeight}px`,
        maxHeight: "60px",
        overflow: `${
          inputRef.current && inputRef.current.scrollHeight > 60
            ? "auto"
            : "hidden"
        }`,
      }}
      value={chatValue}
      onChange={(event): void => {
        setChatValueStore(event.target.value);
      }}
      className={cn(
        fileClass,
        "form-input block w-full border-0 custom-scroll focus:border-0 rounded-none shadow-none focus:ring-0 p-2 sm:text-sm !bg-transparent resize-none outline-none",
      )}
      placeholder={getPlaceholderText(isDragging, noInput)}
    />
  );
};

export default TextAreaWrapper;
