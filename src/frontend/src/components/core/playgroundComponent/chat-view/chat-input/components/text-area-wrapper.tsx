import { useCallback, useEffect, useRef } from "react";
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
const resizeTextarea = (
  textarea: HTMLTextAreaElement,
  value: string,
  previousScrollHeightRef: React.MutableRefObject<number>,
): void => {
  // Reset height to auto to get the correct scrollHeight
  textarea.style.height = "auto";

  // Get the new scroll height
  const scrollHeight = textarea.scrollHeight;
  const previousScrollHeight = previousScrollHeightRef.current;

  // If empty, set minimal height (one line)
  if (!value || value.trim() === "") {
    textarea.style.height = `${CHAT_INPUT_MIN_HEIGHT}px`;
    previousScrollHeightRef.current = CHAT_INPUT_MIN_HEIGHT;
  } else {
    // Only resize if the scroll height changed significantly (more than 1px difference)
    // This prevents tiny resizes on every character that don't change the visual appearance
    if (Math.abs(scrollHeight - previousScrollHeight) > 1) {
      textarea.style.height = `${scrollHeight}px`;
      previousScrollHeightRef.current = scrollHeight;
    } else {
      // Restore the previous height if we're not resizing
      textarea.style.height = `${previousScrollHeight}px`;
    }
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
  const previousScrollHeightRef = useRef<number>(CHAT_INPUT_MIN_HEIGHT);

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
      resizeTextarea(textarea, chatValue, previousScrollHeightRef);
    }
  }, [chatValue, inputRef]);

  const handleChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      const newValue = event.target.value;
      setChatValueStore(newValue);
      // Resize immediately on user input for better UX
      resizeTextarea(event.target, newValue, previousScrollHeightRef);
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
