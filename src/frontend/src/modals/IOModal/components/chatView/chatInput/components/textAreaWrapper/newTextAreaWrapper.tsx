import { useEffect } from "react";
import { Textarea } from "../../../../../../../components/ui/textarea";
import { classNames } from "../../../../../../../utils/utils";

const TextAreaWrapper = ({
  checkSendingOk,
  send,
  lockChat,
  noInput,
  chatValue,
  setChatValue,
  CHAT_INPUT_PLACEHOLDER,
  CHAT_INPUT_PLACEHOLDER_SEND,
  inputRef,
  setInputFocus,
  files,
  isDragging,
}) => {
  const getPlaceholderText = (
    isDragging: boolean,
    noInput: boolean,
  ): string => {
    if (isDragging) {
      return "Drop here";
    } else if (noInput) {
      return CHAT_INPUT_PLACEHOLDER;
    } else {
      return CHAT_INPUT_PLACEHOLDER_SEND;
    }
  };

  const lockClass = lockChat
    ? "form-modal-lock-true bg-input"
    : noInput
      ? "form-modal-no-input bg-input"
      : "form-modal-lock-false bg-background";

  const fileClass = files.length > 0 ? "!rounded-t-none border-t-0" : "";

  const additionalClassNames = "form-modal-lockchat pl-14";

  useEffect(() => {
    if (!lockChat && !noInput) {
      inputRef.current?.focus();
    }
  }, [lockChat, noInput]);

  return (
    <Textarea
      data-testid="input-chat-playground"
      onFocus={(e) => {
        setInputFocus(true);
      }}
      onBlur={() => setInputFocus(false)}
      onKeyDown={(event) => {
        if (checkSendingOk(event)) {
          send();
        }
      }}
      rows={1}
      ref={inputRef}
      disabled={lockChat || noInput}
      style={{
        resize: "none",
        bottom: `${inputRef?.current?.scrollHeight}px`,
        maxHeight: "150px",
        overflow: `${
          inputRef.current && inputRef.current.scrollHeight > 150
            ? "auto"
            : "hidden"
        }`,
      }}
      value={lockChat ? "Thinking..." : chatValue}
      onChange={(event): void => {
        setChatValue(event.target.value);
      }}
      className={classNames(lockClass, fileClass, additionalClassNames)}
      placeholder={getPlaceholderText(isDragging, noInput)}
    />
  );
};

export default TextAreaWrapper;
