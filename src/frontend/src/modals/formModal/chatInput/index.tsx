import { classNames } from "../../../utils";
import { useContext, useEffect, useRef, useState } from "react";
import { TabsContext } from "../../../contexts/tabsContext";
import { Eraser, Lock, LucideSend, Send } from "lucide-react";

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
          "form-input block w-full rounded-md border-gray-300 p-4 pr-16 custom-scroll dark:border-gray-600 sm:text-sm"
        )}
        placeholder={"Send a message..."}
      />
      <div className="absolute bottom-2 right-4">
        <button
          className={classNames(
            "rounded-md p-2 px-1 transition-all duration-300",
            chatValue == "" ? "text-primary" : " bg-indigo-600 text-background"
          )}
          disabled={lockChat}
          onClick={() => sendMessage()}
        >
          {lockChat ? (
            <Lock
              className="ml-1 mr-1 h-5 w-5 animate-pulse"
              aria-hidden="true"
            />
          ) : (
            <LucideSend
              className="mr-2 h-5 w-5 rotate-[44deg] "
              aria-hidden="true"
            />
          )}
        </button>
      </div>
    </div>
  );
}
