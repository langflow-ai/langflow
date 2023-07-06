import { classNames } from "../../../utils";
import { useEffect } from "react";
import { Lock, Send } from "lucide-react";

export default function ChatInput({
  lockChat,
  chatValue,
  sendMessage,
  setChatValue,
  inputRef,
}) {
  useEffect(() => {
    if (!lockChat && inputRef.current) {
      inputRef.current.focus();
    }
  }, [lockChat, inputRef]);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "inherit"; // Reset the height
      inputRef.current.style.height = `${inputRef.current.scrollHeight}px`; // Set it to the scrollHeight
    }
  }, [chatValue]);

  return (
    <div className="relative">
      <textarea
        onKeyDown={(event) => {
          if (event.key === "Enter" && !lockChat && !event.shiftKey) {
            sendMessage();
          }
        }}
        rows={1}
        ref={inputRef}
        disabled={lockChat}
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
        onChange={(e) => {
          setChatValue(e.target.value);
        }}
        className={classNames(
          lockChat
            ? " bg-input text-foreground "
            : "  bg-background text-foreground ",
          "chat-input-modal-txtarea" +
            " input-primary "
        )}
        placeholder={"Send a message..."}
      />
      <div className="chat-input-modal-div">
        <button disabled={lockChat} onClick={() => sendMessage()}>
          {lockChat ? (
            <Lock
              className="chat-input-modal-lock"
              aria-hidden="true"
            />
          ) : (
            <Send
              className="chat-input-modal-send "
              aria-hidden="true"
            />
          )}
        </button>
      </div>
    </div>
  );
}
