import { useUtilityStore } from "@/stores/utilityStore";
import { useEffect } from "react";
import { Textarea } from "../../../../../../components/ui/textarea";
import { classNames } from "../../../../../../utils/utils";

const TextAreaWrapper = ({
  checkSendingOk,
  send,
  isBuilding,
  noInput,
  chatValue,
  CHAT_INPUT_PLACEHOLDER,
  CHAT_INPUT_PLACEHOLDER_SEND,
  inputRef,
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
      return "Send a message...";
    }
  };

  const fileClass = files.length > 0 ? "!rounded-t-none border-t-0" : "";

  const setChatValueStore = useUtilityStore((state) => state.setChatValueStore);

  const additionalClassNames =
    "form-input block w-full border-0 custom-scroll focus:border-ring rounded-none shadow-none focus:ring-0 p-0 sm:text-sm !bg-transparent";

  useEffect(() => {
    if (!isBuilding && !noInput) {
      inputRef.current?.focus();
    }
  }, [isBuilding, noInput]);

  return (
    <Textarea
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
        maxHeight: "150px",
        overflow: `${
          inputRef.current && inputRef.current.scrollHeight > 150
            ? "auto"
            : "hidden"
        }`,
      }}
      value={chatValue}
      onChange={(event): void => {
        setChatValueStore(event.target.value);
      }}
      className={classNames(fileClass, additionalClassNames)}
      placeholder={getPlaceholderText(isDragging, noInput)}
    />
  );
};

export default TextAreaWrapper;
