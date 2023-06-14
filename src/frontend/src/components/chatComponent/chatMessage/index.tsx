import {
  ChatBubbleLeftEllipsisIcon,
  ChatBubbleOvalLeftEllipsisIcon,
  PlusSmallIcon,
} from "@heroicons/react/24/outline";
import { useState } from "react";
import { ChatMessageType } from "../../../types/chat";
import { nodeColors } from "../../../utils";
import Convert from "ansi-to-html";
const convert = new Convert({ newline: true });

export default function ChatMessage({ chat }: { chat: ChatMessageType }) {
  const [hidden, setHidden] = useState(true);
  return (
    <div>
      {!chat.isSend ? (
        <div className="w-full text-start">
          <div
            style={{ backgroundColor: nodeColors["chat"] }}
            className=" relative text-start inline-block text-white rounded-xl overflow-hidden w-fit max-w-[280px] text-sm font-normal rounded-tl-none"
          >
            {hidden && chat.thought && chat.thought !== "" && (
              <div
                onClick={() => setHidden((prev) => !prev)}
                className="absolute top-2 right-2 cursor-pointer"
              >
                <ChatBubbleOvalLeftEllipsisIcon className="w-5 h-5 animate-bounce" />
              </div>
            )}
            {chat.thought && chat.thought !== "" && !hidden && (
              <div
                onClick={() => setHidden((prev) => !prev)}
                style={{ backgroundColor: nodeColors["thought"] }}
                className=" text-start inline-block w-full pb-3 pt-3 px-5 cursor-pointer"
                dangerouslySetInnerHTML={{
                  __html: convert.toHtml(chat.thought),
                }}
              ></div>
            )}
            {chat.thought && chat.thought !== "" && !hidden && <br></br>}
            <div
              className="w-full rounded-b-md px-4 pb-3 pt-3 pr-8"
              style={{ backgroundColor: nodeColors["chat"] }}
            >
              {chat.message}
            </div>
          </div>
        </div>
      ) : (
        <div className="w-full text-end">
          <div className="text-start inline-block rounded-xl p-3 overflow-hidden w-fit max-w-[280px] px-5 text-sm text-black dark:text-white dark:bg-gray-700 bg-gray-200 font-normal rounded-tr-none">
            {chat.message}
          </div>
        </div>
      )}
    </div>
  );
}
