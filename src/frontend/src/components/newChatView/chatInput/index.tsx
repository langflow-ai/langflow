import { useEffect, useState } from "react";
import IconComponent from "../../../components/genericIconComponent";
import { Textarea } from "../../../components/ui/textarea";
import { chatInputType } from "../../../types/components";
import { classNames } from "../../../utils/utils";

export default function ChatInput({
  lockChat,
  chatValue,
  sendMessage,
  setChatValue,
  inputRef,
  noInput,
}: chatInputType): JSX.Element {
  const [repeat, setRepeat] = useState(1);
  useEffect(() => {
    if (!lockChat && inputRef.current) {
      inputRef.current.focus();
    }
  }, [lockChat, inputRef]);

  function handleChange(value: number) {
    console.log(value);
    if (value > 0) {
      setRepeat(value);
    } else {
      setRepeat(1);
    }
  }

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "inherit"; // Reset the height
      inputRef.current.style.height = `${inputRef.current.scrollHeight}px`; // Set it to the scrollHeight
    }
  }, [chatValue]);

  return (
    <div className="flex w-full gap-2">
      <div className="relative w-full">
        <Textarea
          onKeyDown={(event) => {
            if (event.key === "Enter" && !lockChat && !event.shiftKey) {
              sendMessage(repeat);
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
          className={classNames(
            lockChat
              ? " form-modal-lock-true bg-input"
              : noInput
              ? "form-modal-no-input bg-input"
              : " form-modal-lock-false bg-background",

            "form-modal-lockchat"
          )}
          placeholder={
            noInput
              ? "No chat input variables found. Click to run your flow."
              : "Send a message..."
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
            disabled={lockChat}
            onClick={(): void => sendMessage(repeat)}
          >
            {lockChat ? (
              <IconComponent
                name="Lock"
                className="form-modal-lock-icon"
                aria-hidden="true"
              />
            ) : noInput ? (
              <IconComponent
                name="Play"
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
