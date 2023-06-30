import { classNames } from "../../../utils";
import { useContext, useEffect, useRef, useState } from "react";
import { TabsContext } from "../../../contexts/tabsContext";
import { INPUT_STYLE } from "../../../constants";
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
          "p-4 form-input block w-full custom-scroll rounded-md border-gray-300 dark:border-gray-600 pr-16 sm:text-sm" +
            INPUT_STYLE
        )}
        placeholder={"Send a message..."}
      />
      <div className="absolute bottom-2 right-4">
        <button className={classNames("p-2 px-1 transition-all duration-300 rounded-md",chatValue == "" ? "text-primary" : " bg-indigo-600 text-background")} disabled={lockChat} onClick={() => sendMessage()}>
          {lockChat ? (
            <Lock
              className="h-5 w-5 ml-1 mr-1 animate-pulse"
              aria-hidden="true"
            />
          ) : (
            <LucideSend
              className="h-5 w-5 mr-2 rotate-[44deg] "
              aria-hidden="true"
            />
          )}
        </button>
      </div>
    </div>
  );
}
