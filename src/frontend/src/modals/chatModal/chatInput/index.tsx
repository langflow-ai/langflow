import { LockClosedIcon, PaperAirplaneIcon } from "@heroicons/react/24/outline";
import { classNames } from "../../../utils";
import { useContext, useEffect, useRef, useState } from "react";
import { TabsContext } from "../../../contexts/tabsContext";
import { INPUT_STYLE } from "../../../constants";
export default function ChatInput({
  lockChat,
  chatValue,
  sendMessage,
  setChatValue,
  inputRef,
}) {
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
            ? " bg-input text-black dark:bg-almost-dark-gray dark:text-medium-low-gray"
            : "  bg-white-200 text-black dark:bg-high-dark-gray dark:text-medium-low-gray",
          "form-input block w-full custom-scroll rounded-md border-medium-low-gray dark:border-medium-dark-gray pr-10 sm:text-sm" +
            INPUT_STYLE
        )}
        placeholder={"Send a message..."}
      />
      <div className="absolute bottom-0.5 right-3">
        <button disabled={lockChat} onClick={() => sendMessage()}>
          {lockChat ? (
            <LockClosedIcon
              className="h-5 w-5 text-medium-gray  dark:hover:text-medium-low-gray animate-pulse"
              aria-hidden="true"
            />
          ) : (
            <PaperAirplaneIcon
              className="h-5 w-5 text-medium-gray hover:text-medium-dark-gray dark:hover:text-medium-low-gray"
              aria-hidden="true"
            />
          )}
        </button>
      </div>
    </div>
  );
}
