import { ChatBubbleOvalLeftEllipsisIcon } from "@heroicons/react/24/outline";
import { useState } from "react";
import { ChatMessageType } from "../../../types/chat";
import { classNames } from "../../../utils";
import AiIcon from "../../../assets/Gooey Ring-5s-271px.svg";
import { UserIcon } from "@heroicons/react/24/solid";
import FileCard from "../fileComponent";
var Convert = require("ansi-to-html");
var convert = new Convert({ newline: true });

export default function ChatMessage({ chat }: { chat: ChatMessageType }) {
  const [hidden, setHidden] = useState(true);
  return (
    <div
      className={classNames(
        "w-full py-2 pl-2 flex",
        chat.isSend ? "bg-white dark:bg-gray-800 " : "bg-gray-200  dark:bg-gray-700"
      )}
    >
      <div
        className={classNames(
          "rounded-full w-8 h-8 flex items-center my-3 justify-center",
          chat.isSend ? "bg-gray-900" : "bg-gray-200"
        )}
      >
        {!chat.isSend && <img className="scale-150" src={AiIcon} />}
        {chat.isSend && <UserIcon className="w-6 h-6 -mb-1 text-gray-200" />}
      </div>
      {!chat.isSend ? (
        <div className="w-full text-start flex items-center">
          <div className="w-full relative text-start inline-block text-gray-600 text-sm font-normal">
            {hidden && chat.thought && chat.thought !== "" && (
              <div
                onClick={() => setHidden((prev) => !prev)}
                className="absolute -top-1 -left-2 cursor-pointer"
              >
                <ChatBubbleOvalLeftEllipsisIcon className="w-5 h-5 animate-bounce dark:text-white" />
              </div>
            )}
            {chat.thought && chat.thought !== "" && !hidden && (
              <div
                onClick={() => setHidden((prev) => !prev)}
                className=" text-start inline-block rounded-md  h-full border border-gray-300
								bg-gray-100 w-[95%] pb-3 pt-3 px-2 ml-3 cursor-pointer scrollbar-hide overflow-scroll"
                dangerouslySetInnerHTML={{
                  __html: convert.toHtml(chat.thought),
                }}
              ></div>
            )}
            {chat.thought && chat.thought !== "" && !hidden && <br></br>}
            <div className="w-full px-4 pb-3 pt-3 pr-8">
              <span className="dark:text-white">
                {chat.message}
                {chat.files && (
                  <div className="my-2 w-full">
                    {chat.files.map((file, index) => {
                      return (
                        <div key={index} className="my-2 w-full">
                          <FileCard
                            fileName={"Generated File"}
                            fileType={file.data_type}
                            content={file.data}
                          />
                        </div>
                      );
                    })}
                  </div>
                )}
              </span>
            </div>
          </div>
        </div>
      ) : (
        <div className="w-full flex items-center">
          <div className="text-start inline-block px-3 text-sm text-gray-600 dark:text-white">
            {chat.message}
          </div>
        </div>
      )}
    </div>
  );
}
