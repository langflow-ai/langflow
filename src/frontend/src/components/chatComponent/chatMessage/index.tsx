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
  const convert = new Convert({ newline: true });
  const [hidden, setHidden] = useState(true);
  return (
    <div>
      {!chat.isSend ? (
        <div className="w-full text-start">
          <div
            style={{ backgroundColor: nodeColors["chat"] }}
            className=" relative inline-block w-fit max-w-[280px] overflow-hidden rounded-xl rounded-tl-none text-start text-sm font-normal text-white"
          >
            {hidden && chat.thought && chat.thought !== "" && (
              <div
                onClick={() => setHidden((prev) => !prev)}
                className="absolute right-2 top-2 cursor-pointer"
              >
                <ChatBubbleOvalLeftEllipsisIcon className="h-5 w-5 animate-bounce" />
              </div>
            )}
            {chat.thought && chat.thought !== "" && !hidden && (
              <div
                onClick={() => setHidden((prev) => !prev)}
                style={{ backgroundColor: nodeColors["thought"] }}
                className=" inline-block w-full cursor-pointer px-5 pb-3 pt-3 text-start"
                dangerouslySetInnerHTML={{
                  __html: convert.toHtml(chat.thought),
                }}
              ></div>
            )}
            {chat.thought && chat.thought !== "" && !hidden && <br></br>}
            <div
              className="w-full rounded-b-md px-4 pb-3 pr-8 pt-3"
              style={{ backgroundColor: nodeColors["chat"] }}
            >
              {chat.message}
            </div>
          </div>
        </div>
      ) : (
        <div className="w-full text-end">
          <div className="inline-block w-fit max-w-[280px] overflow-hidden rounded-xl rounded-tr-none bg-gray-200 p-3 px-5 text-start text-sm font-normal text-black dark:bg-gray-700 dark:text-white">
            {chat.message}
          </div>
        </div>
      )}
    </div>
  );
}
