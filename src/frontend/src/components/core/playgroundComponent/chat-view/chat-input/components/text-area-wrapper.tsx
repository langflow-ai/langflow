import { useCallback, useEffect } from "react";
import { CHAT_INPUT_MIN_HEIGHT } from "@/constants/constants";
import { useUtilityStore } from "@/stores/utilityStore";
import type { FilePreviewType } from "@/types/components";
import { Textarea } from "../../../../../../components/ui/textarea";
import { classNames } from "../../../../../../utils/utils";

interface TextAreaWrapperProps {
  checkSendingOk: (event: React.KeyboardEvent<HTMLTextAreaElement>) => boolean;
  send: () => void;
  isBuilding: boolean;
  noInput: boolean;
  chatValue: string;
  CHAT_INPUT_PLACEHOLDER: string;
  inputRef: React.RefObject<HTMLTextAreaElement>;
  files: FilePreviewType[];
  isDragging: boolean;
}

//Resizes a textarea element to fit its content, with a minimum height when empty.
const resizeTextarea = (textarea: HTMLTextAreaElement, value: string): void => {
  // Reset height to auto to get the correct scrollHeight
  textarea.style.height = "auto";

  // If empty, set minimal height (one line)
  if (!value || value.trim() === "") {
    textarea.style.height = `${CHAT_INPUT_MIN_HEIGHT}px`;
  } else {
    // Set height to scrollHeight to fit all content
    textarea.style.height = `${textarea.scrollHeight}px`;
  }

  // Ensure no overflow and no max-height constraint
  textarea.style.overflowY = "hidden";
  textarea.style.maxHeight = "none";
};

const TextAreaWrapper = ({
  checkSendingOk,
  send,
  isBuilding,
  noInput,
  chatValue,
  CHAT_INPUT_PLACEHOLDER,
  inputRef,
  files,
  isDragging,
}: TextAreaWrapperProps) => {
  const setChatValueStore = useUtilityStore((state) => state.setChatValueStore);

  const getPlaceholderText = useCallback((): string => {
    if (isDragging) {
      return "Drop here";
    }
    if (noInput) {
      return CHAT_INPUT_PLACEHOLDER;
    }
    return "Send a message...";
  }, [isDragging, noInput, CHAT_INPUT_PLACEHOLDER]);

  const fileClass = files.length > 0 ? "!rounded-t-none border-t-0" : "";

  const additionalClassNames =
    "form-input block w-full border-0 custom-scroll focus:border-ring rounded-none shadow-none focus:ring-0 p-0 sm:text-sm !bg-transparent resize-none overflow-hidden !max-h-none";

  // Auto-focus when not building and input is enabled
  useEffect(() => {
    if (!isBuilding && !noInput) {
      inputRef.current?.focus();
    }
  }, [isBuilding, noInput, inputRef]);

  // Resize textarea whenever chatValue changes (handles programmatic changes like clearing after send)
  // Note: handleChange handles resize for user input, but this ensures programmatic changes also resize
  useEffect(() => {
    const textarea = inputRef.current;
    if (textarea) {
      resizeTextarea(textarea, chatValue);
    }
  }, [chatValue, inputRef]);

  const handleChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      const newValue = event.target.value;
      setChatValueStore(newValue);
      // Resize immediately on user input for better UX
      resizeTextarea(event.target, newValue);
    },
    [setChatValueStore],
  );

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (checkSendingOk(event)) {
        event.preventDefault();
        send();
      }
    },
    [checkSendingOk, send],
  );

  return (
    <Textarea
      data-testid="input-chat-playground"
      onKeyDown={handleKeyDown}
      rows={1}
      ref={inputRef}
      disabled={isBuilding || noInput}
      value={chatValue}
      onChange={handleChange}
      className={classNames(fileClass, additionalClassNames)}
      placeholder={getPlaceholderText()}
    />
  );
};

export default TextAreaWrapper;
