import { useCallback, useEffect, useRef } from "react";
import {
  CHAT_INPUT_MIN_HEIGHT,
  CHAT_INPUT_MAX_HEIGHT,
} from "@/constants/constants";
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

//Resizes a textarea element to fit its content, with a minimum and maximum height constraint.
const resizeTextarea = (textarea: HTMLTextAreaElement, value: string): void => {
  // Collapse to 0 so scrollHeight reflects only the content, not the container
  textarea.style.height = "0px";
  const scrollHeight = textarea.scrollHeight;

  if (!value || value.trim() === "") {
    textarea.style.height = `${CHAT_INPUT_MIN_HEIGHT}px`;
    textarea.style.overflowY = "hidden";
  } else {
    const newHeight = Math.max(
      CHAT_INPUT_MIN_HEIGHT,
      Math.min(scrollHeight, CHAT_INPUT_MAX_HEIGHT),
    );
    textarea.style.height = `${newHeight}px`;
    textarea.style.overflowY =
      scrollHeight > CHAT_INPUT_MAX_HEIGHT ? "auto" : "hidden";
  }
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
    "form-input block w-full border-0 custom-scroll focus:border-ring rounded-none shadow-none focus:ring-0 p-0 sm:text-sm !bg-transparent resize-none";

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

  const chatValueRef = useRef(chatValue);
  const previousWidthRef = useRef<number>(0);

  useEffect(() => {
    chatValueRef.current = chatValue;
  }, [chatValue]);

  useEffect(() => {
    const textarea = inputRef.current;
    if (!textarea) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width !== previousWidthRef.current) {
          previousWidthRef.current = entry.contentRect.width;
          resizeTextarea(textarea, chatValueRef.current);
        }
      }
    });

    resizeObserver.observe(textarea);

    return () => {
      resizeObserver.disconnect();
    };
  }, [inputRef]);

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
      style={{ maxHeight: `${CHAT_INPUT_MAX_HEIGHT}px` }}
    />
  );
};

export default TextAreaWrapper;
