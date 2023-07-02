import { useEffect, useRef, useState } from "react";
import { ChatMessageType } from "../../../types/chat";
import { classNames } from "../../../utils";
import AiIcon from "../../../assets/Gooey Ring-5s-271px.svg";
import AiIconStill from "../../../assets/froze-flow.png";
import FileCard from "../fileComponent";
import ReactMarkdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { CodeBlock } from "./codeBlock";
import Convert from "ansi-to-html";
import { User2, MessageCircle } from "lucide-react";
import DOMPurify from "dompurify";
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
        "flex w-full py-2 pl-2",
        chat.isSend ? "bg-background " : "bg-input"
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
              src={lastMessage ? AiIcon : AiIconStill}
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
        {chat.isSend && <User2 className="-mb-1 h-6 w-6 text-primary " />}
      </div>
      {!chat.isSend ? (
        <div className="flex w-full items-center text-start">
          <div className="relative inline-block w-full text-start text-sm  font-normal text-muted-foreground">
            {hidden && chat.thought && chat.thought !== "" && (
              <div
                onClick={() => setHidden((prev) => !prev)}
                className="absolute -left-2 -top-1 cursor-pointer"
              >
                <MessageCircle className="h-5 w-5 animate-bounce " />
              </div>
            )}
            {chat.thought && chat.thought !== "" && !hidden && (
              <div
                onClick={() => setHidden((prev) => !prev)}
                className=" ml-3 inline-block h-full w-[95%]  cursor-pointer overflow-scroll rounded-md
								border border-ring bg-muted px-2 pb-3 pt-3 text-start text-muted-foreground scrollbar-hide"
                dangerouslySetInnerHTML={{
                  __html: DOMPurify.sanitize(convert.toHtml(chat.thought)),
                }}
              ></div>
            )}
            {chat.thought && chat.thought !== "" && !hidden && <br></br>}
            <div className="w-full px-4 pb-3 pr-8 pt-3">
              <div className="w-full">
                <div className="w-full">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkMath]}
                    rehypePlugins={[rehypeMathjax]}
                    className="markdown prose text-muted-foreground "
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
          <div className="inline-block px-3 text-start text-muted-foreground ">
            {message.split("\n").map((line, index) => (
              <span key={index} className="text-muted-foreground ">
                {line}
                <br />
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
