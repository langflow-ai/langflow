import { Textarea } from "../../../../../../../components/ui/textarea";
import { classNames } from "../../../../../../../utils/utils";

const TextAreaWrapper = ({
  dragOver,
  dragEnter,
  dragLeave,
  onDrop,
  checkSendingOk,
  send,
  lockChat,
  noInput,
  saveLoading,
  chatValue,
  setChatValue,
  CHAT_INPUT_PLACEHOLDER,
  CHAT_INPUT_PLACEHOLDER_SEND,
  inputRef,
  setInputFocus,
  files,
}) => {
  return (
    <Textarea
      onFocus={(e) => {
        setInputFocus(true);
        e.target.style.borderTopWidth = "0";
      }}
      onBlur={() => setInputFocus(false)}
      onDragOver={dragOver}
      onDragEnter={dragEnter}
      onDragLeave={dragLeave}
      onDrop={onDrop}
      onKeyDown={(event) => {
        if (checkSendingOk(event)) {
          send();
        }
      }}
      rows={1}
      ref={inputRef}
      disabled={lockChat || noInput || saveLoading}
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
      value={lockChat ? "Thinking..." : saveLoading ? "Saving..." : chatValue}
      onChange={(event): void => {
        setChatValue(event.target.value);
      }}
      className={classNames(
        lockChat || saveLoading
          ? " form-modal-lock-true bg-input"
          : noInput
            ? "form-modal-no-input bg-input"
            : " form-modal-lock-false bg-background",

        "form-modal-lockchat",
        `${
          files.length > 0
            ? "rounded-b-md border-t-0 border-border focus:border-t-0 focus:border-ring"
            : "rounded-md border-t-2 border-border focus:border-ring"
        }`,
        "pl-10",
      )}
      placeholder={
        noInput ? CHAT_INPUT_PLACEHOLDER : CHAT_INPUT_PLACEHOLDER_SEND
      }
    />
  );
};

export default TextAreaWrapper;
