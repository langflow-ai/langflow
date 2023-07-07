import { classNames } from "../../../utils";
import { useContext, useEffect, useRef, useState } from "react";
import { TabsContext } from "../../../contexts/tabsContext";
import { Eraser, Lock, LucideSend } from "lucide-react";

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
            ? " form-modal-lock-true"
            : " form-modal-lock-false",
          "form-modal-lockchat"
        )}
        placeholder={"Send a message..."}
      />
      <div className="form-modal-send-icon-position">
        <button
          className={classNames(
            "form-modal-send-button",
            chatValue == "" ? "text-primary" : " bg-indigo-600 text-background"
          )}
          disabled={lockChat}
          onClick={() => sendMessage()}
        >
          {lockChat ? (
            <Lock
              className="form-modal-lock-icon"
              aria-hidden="true"
            />
          ) : (
            <LucideSend
              className="form-modal-send-icon "
              aria-hidden="true"
            />
          )}
        </button>
      </div>
    </div>
  );
}
