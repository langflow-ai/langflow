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
}: {
  chat: ChatMessageType;
  lockChat: boolean;
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
        "flex w-full py-2 pl-2",
        chat.isSend
          ? "bg-white dark:bg-gray-900 "
          : "bg-gray-200  dark:bg-gray-800"
      )}
    >
      <div
        className={classNames(
          "my-3 flex h-8 w-8 items-center justify-center overflow-hidden rounded-full"
        )}
      >
        {!chat.isSend && (
          <div className="relative h-8 w-8">
            <img
              className={
                "absolute scale-150 transition-opacity duration-500 " +
                (lockChat ? "opacity-100" : "opacity-0")
              }
              src={AiIcon}
            />
            <img
              className={
                "absolute scale-150 transition-opacity duration-500 " +
                (lockChat ? "opacity-0" : "opacity-100")
              }
              src={AiIconStill}
            />
          </div>
        )}
        {chat.isSend && (
          <UserIcon className="-mb-1 h-6 w-6 text-gray-800 dark:text-gray-200" />
        )}
      </div>
      {!chat.isSend ? (
        <div className="flex w-full items-center text-start">
          <div className="relative inline-block w-full text-start text-sm font-normal text-gray-600 dark:text-gray-300">
            {hidden && chat.thought && chat.thought !== "" && (
              <div
                onClick={() => setHidden((prev) => !prev)}
                className="absolute -left-2 -top-1 cursor-pointer"
              >
                <ChatBubbleOvalLeftEllipsisIcon className="h-5 w-5 animate-bounce dark:text-white" />
              </div>
            )}
            {chat.thought && chat.thought !== "" && !hidden && (
              <div
                onClick={() => setHidden((prev) => !prev)}
                className=" ml-3 inline-block h-full w-[95%] cursor-pointer overflow-scroll rounded-md border border-gray-300
								bg-gray-100 px-2 pb-3 pt-3 text-start text-gray-600 scrollbar-hide dark:border-gray-500 dark:bg-gray-800 dark:text-gray-200"
                dangerouslySetInnerHTML={{
                  __html: convert.toHtml(chat.thought),
                }}
              ></div>
            )}
            {chat.thought && chat.thought !== "" && !hidden && <br></br>}
            <div className="w-full px-4 pb-3 pr-8 pt-3">
              <div className="w-full dark:text-white">
                <div className="w-full">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkMath]}
                    rehypePlugins={[rehypeMathjax]}
                    className="markdown prose text-gray-600 dark:prose-invert dark:text-gray-200"
                    components={{
                      code({ node, inline, className, children, ...props }) {
                        if (children.length) {
                          if (children[0] == "▍") {
                            return (
                              <span className="mt-1 animate-pulse cursor-default">
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
        <div className="flex w-full items-center">
          <div className="inline-block px-3 text-start text-sm text-gray-600 dark:text-white">
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkMath]}
              rehypePlugins={[rehypeMathjax]}
              className="markdown prose text-gray-600 dark:prose-invert dark:text-gray-200"
            >
              {message}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}
