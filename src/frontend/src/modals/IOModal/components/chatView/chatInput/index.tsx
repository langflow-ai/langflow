import { useEffect, useState } from "react";
import IconComponent from "../../../../../components/genericIconComponent";
import { Textarea } from "../../../../../components/ui/textarea";
import {
  CHAT_INPUT_PLACEHOLDER,
  CHAT_INPUT_PLACEHOLDER_SEND,
} from "../../../../../constants/constants";
import useFlowsManagerStore from "../../../../../stores/flowsManagerStore";
import { chatInputType } from "../../../../../types/components";
import { classNames } from "../../../../../utils/utils";
import { uploadFile } from "../../../../../controllers/API";

export default function ChatInput({
  lockChat,
  chatValue,
  sendMessage,
  setChatValue,
  inputRef,
  noInput,
}: chatInputType): JSX.Element {
  const [repeat, setRepeat] = useState(1);
  const saveLoading = useFlowsManagerStore((state) => state.saveLoading);
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  useEffect(() => {
    if (!lockChat && inputRef.current) {
      inputRef.current.focus();
    }
  }, [lockChat, inputRef]);

  useEffect(() => {
    if (inputRef.current && inputRef.current.scrollHeight !== 0) {
      inputRef.current.style.height = "inherit"; // Reset the height
      inputRef.current.style.height = `${inputRef.current.scrollHeight}px`; // Set it to the scrollHeight
    }
  }, [chatValue]);

  //listen to ctrl-v to paste images
  useEffect(() => {
    const handlePaste = (event: ClipboardEvent): void => {
      const items = event.clipboardData?.items;
      if (items) {
        for (let i = 0; i < items.length; i++) {
          if (items[i].type.indexOf("image") !== -1) {
            const blob = items[i].getAsFile();
            if (blob) {
              // const reader = new FileReader();
              // reader.onload = (e) => {
              //   const data = e.target?.result;
              //   if (typeof data === "string") {
              //     // sendMessage(data);
              //   }
              // };
              // reader.readAsDataURL(blob);
              uploadFile(blob, currentFlowId).then((res) => {
                console.log(res);
              });
            }
          }
        }
      }
    };
    document.addEventListener("paste", handlePaste);
    return () => {
      document.removeEventListener("paste", handlePaste);
    };
  }, []);

  return (
    <div className="flex w-full gap-2">
      <div className="relative w-full">
        <Textarea
          onKeyDown={(event) => {
            if (
              event.key === "Enter" &&
              !lockChat &&
              !saveLoading &&
              !event.shiftKey &&
              !event.nativeEvent.isComposing
            ) {
              sendMessage(repeat);
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
          value={
            lockChat ? "Thinking..." : saveLoading ? "Saving..." : chatValue
          }
          onChange={(event): void => {
            setChatValue(event.target.value);
          }}
          className={classNames(
            lockChat || saveLoading
              ? " form-modal-lock-true bg-input"
              : noInput
              ? "form-modal-no-input bg-input"
              : " form-modal-lock-false bg-background",

            "form-modal-lockchat"
          )}
          placeholder={
            noInput ? CHAT_INPUT_PLACEHOLDER : CHAT_INPUT_PLACEHOLDER_SEND
          }
        />
        <div className="form-modal-send-icon-position">
          <button
            className={classNames(
              "form-modal-send-button",
              noInput
                ? "bg-high-indigo text-background"
                : chatValue === ""
                ? "text-primary"
                : "bg-chat-send text-background"
            )}
            disabled={lockChat || saveLoading}
            onClick={(): void => sendMessage(repeat)}
          >
            {lockChat || saveLoading ? (
              <IconComponent
                name="Lock"
                className="form-modal-lock-icon"
                aria-hidden="true"
              />
            ) : noInput ? (
              <IconComponent
                name="Zap"
                className="form-modal-play-icon"
                aria-hidden="true"
              />
            ) : (
              <IconComponent
                name="LucideSend"
                className="form-modal-send-icon "
                aria-hidden="true"
              />
            )}
          </button>
        </div>
      </div>
      {/* 
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="primary" className="h-13 px-4">
            <IconComponent name="Repeat" className="" aria-hidden="true" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-fit">
          <div className="flex flex-col items-center justify-center gap-2">
            <span className="text-sm">Repetitions: </span>
            <Input
              onChange={(e) => {
                handleChange(parseInt(e.target.value));
              }}
              className="w-16"
              type="number"
              min={0}
            />
          </div>
        </PopoverContent>
      </Popover> */}
    </div>
  );
}
