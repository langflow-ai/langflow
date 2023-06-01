import { ChatBubbleOvalLeftEllipsisIcon } from "@heroicons/react/24/outline";
import { useEffect, useRef, useState } from "react";
import { ChatMessageType } from "../../../types/chat";
import { classNames } from "../../../utils";
import AiIcon from "../../../assets/Gooey Ring-5s-271px.svg";
import AiIconStill from "../../../assets/froze-flow.png";
import { UserIcon } from "@heroicons/react/24/solid";
import FileCard from "../fileComponent";
import ReactMarkdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { CodeBlock } from "./codeBlock";
import Convert from "ansi-to-html";

export default function ChatMessage({
  chat,
  lockChat,
  lastMessage,
}: {
  chat: ChatMessageType;
  lockChat: boolean;
  lastMessage: boolean;
}) {
  const convert = new Convert({ newline: true });
  const [message, setMessage] = useState("");
  const imgRef = useRef(null);
  useEffect(() => {
    setMessage(chat.message);
  }, [chat.message]);
  const [hidden, setHidden] = useState(true);
  return (
    <div
      className={classNames(
        "w-full py-2 pl-2 flex",
        chat.isSend
          ? "bg-white dark:bg-gray-900 "
          : "bg-gray-200  dark:bg-gray-800"
      )}
    >
      <div
        className={classNames(
          "rounded-full overflow-hidden w-8 h-8 flex items-center my-3 justify-center"
        )}
      >
        {!chat.isSend && (
          <div className="relative w-8 h-8">
            <img
              className={
                "absolute transition-opacity duration-500 scale-150 " +
                (lockChat ? "opacity-100" : "opacity-0")
              }
              src={lastMessage ? AiIcon : AiIconStill}
            />
            <img
              className={
                "absolute transition-opacity duration-500 scale-150 " +
                (lockChat ? "opacity-0" : "opacity-100")
              }
              src={AiIconStill}
            />
          </div>
        )}
        {chat.isSend && (
          <UserIcon className="w-6 h-6 -mb-1 text-gray-800 dark:text-gray-200" />
        )}
      </div>
      {!chat.isSend ? (
        <div className="w-full text-start flex items-center">
          <div className="w-full relative text-start inline-block text-gray-600 dark:text-gray-300 text-sm font-normal">
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
                className=" text-start inline-block rounded-md text-gray-600 dark:text-gray-200 h-full border border-gray-300 dark:border-gray-500
								bg-gray-100 dark:bg-gray-800 w-[95%] pb-3 pt-3 px-2 ml-3 cursor-pointer scrollbar-hide overflow-scroll"
                dangerouslySetInnerHTML={{
                  __html: convert.toHtml(chat.thought),
                }}
              ></div>
            )}
            {chat.thought && chat.thought !== "" && !hidden && <br></br>}
            <div className="w-full px-4 pb-3 pt-3 pr-8">
              <div className="dark:text-white w-full">
                <div className="w-full">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkMath]}
                    rehypePlugins={[rehypeMathjax]}
                    className="markdown prose dark:prose-invert text-gray-600 dark:text-gray-200"
                    components={{
                      code({ node, inline, className, children, ...props }) {
                        if (children.length) {
                          if (children[0] == "▍") {
                            return (
                              <span className="animate-pulse cursor-default mt-1">
                                ▍
                              </span>
                            );
                          }

                          children[0] = (children[0] as string).replace(
                            "`▍`",
                            "▍"
                          );
                        }

                        const match = /language-(\w+)/.exec(className || "");

                        return !inline ? (
                          <CodeBlock
                            key={Math.random()}
                            language={(match && match[1]) || ""}
                            value={String(children).replace(/\n$/, "")}
                            {...props}
                          />
                        ) : (
                          <code className={className} {...props}>
                            {children}
                          </code>
                        );
                      },
                    }}
                  >
                    {message}
                  </ReactMarkdown>
                </div>
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
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="w-full flex items-center">
          <div className="text-start inline-block px-3 text-sm text-gray-600 dark:text-white">
            <span
              className="text-gray-600 dark:text-gray-200"
              dangerouslySetInnerHTML={{
                __html: message.replace(/\n/g, "<br>"),
              }}
            ></span>
          </div>
        </div>
      )}
    </div>
  );
}
