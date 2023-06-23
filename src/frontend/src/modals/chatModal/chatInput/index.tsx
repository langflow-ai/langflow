import { classNames } from "../../../utils";
import { useContext, useEffect, useRef, useState } from "react";
import { TabsContext } from "../../../contexts/tabsContext";
import { INPUT_STYLE } from "../../../constants";
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
            ? " bg-input text-black dark:bg-gray-700 dark:text-gray-300"
            : "  bg-white-200 text-black dark:bg-gray-900 dark:text-gray-300",
          "form-input block w-full custom-scroll rounded-md border-gray-300 dark:border-gray-600 pr-10 sm:text-sm" +
            INPUT_STYLE
        )}
        placeholder={"Send a message..."}
      />
      <div className="absolute bottom-0.5 right-3">
        <button disabled={lockChat} onClick={() => sendMessage()}>
          {lockChat ? (
            <Lock
              className="h-5 w-5 text-gray-500  dark:hover:text-gray-300 animate-pulse"
              aria-hidden="true"
            />
          ) : (
            <Send
              className="h-5 w-5 text-gray-500 hover:text-gray-600 dark:hover:text-gray-300"
              aria-hidden="true"
            />
          )}
        </button>
      </div>
    </div>
  );
}
