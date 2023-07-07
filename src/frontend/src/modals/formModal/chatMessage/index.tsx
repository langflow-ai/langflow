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
import {
  User2,
  MessageSquare,
  ChevronDown,
  MessageCircle,
  MessageSquareDashed,
} from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../../../components/ui/accordion";
import { Badge } from "../../../components/ui/badge";
import { THOUGHTS_ICON } from "../../../constants";

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
  const [hidden, setHidden] = useState(true);
  const [template, setTemplate] = useState(chat.template);
  const [promptOpen, setPromptOpen] = useState(false);
  return (
    <div
      className={classNames(
        "flex w-full px-2 py-6 pl-4 pr-9",
        chat.isSend ? "" : " "
      )}
    >
      <div className={classNames("mb-3 ml-3 mr-6 mt-1 ")}>
        {!chat.isSend ? (
          <div className="flex flex-col items-center gap-1">
            <div className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-md bg-[#afe6ef] p-5 text-2xl ">
              🤖
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1">
            <div className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-md bg-[#aface9] p-5 text-2xl ">
              👨‍💻
            </div>
          </div>
        )}
      </div>
      {!chat.isSend ? (
        <div className="flex w-full flex-1 text-start">
          <div className="relative inline-block w-full text-start text-sm font-normal text-muted-foreground">
            {hidden && chat.thought && chat.thought !== "" && (
              <div
                onClick={() => setHidden((prev) => !prev)}
                className="absolute -left-8 -top-3 cursor-pointer"
              >
                <THOUGHTS_ICON className="h-4 w-4 animate-bounce dark:text-white" />
              </div>
            )}
            {chat.thought && chat.thought !== "" && !hidden && (
              <div
                onClick={() => setHidden((prev) => !prev)}
                className=" ml-3 inline-block h-full w-[95%] cursor-pointer overflow-scroll rounded-md border
								border-gray-300 bg-muted px-2 text-start text-primary scrollbar-hide dark:border-gray-500 dark:bg-gray-800"
                dangerouslySetInnerHTML={{
                  __html: convert.toHtml(chat.thought),
                }}
              ></div>
            )}
            {chat.thought && chat.thought !== "" && !hidden && <br></br>}
            <div className="w-full">
              <div className="w-full dark:text-white">
                <div className="w-full">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkMath]}
                    rehypePlugins={[rehypeMathjax]}
                    className="markdown prose inline-block break-words text-primary
                     dark:prose-invert"
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
                    {chat.message.toString()}
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
        <div>
          <button
            className="mb-2 flex items-center gap-4 rounded-md border border-ring/60 bg-background px-4 py-3 text-base font-semibold"
            onClick={() => {
              setPromptOpen((old) => !old);
            }}
          >
            Initial Prompt
            <ChevronDown
              className={
                "h-3 w-3 transition-all " + (promptOpen ? "rotate-180" : "")
              }
            />
          </button>
          <span className="prose inline-block break-words text-primary dark:prose-invert">
            {promptOpen
              ? template.split("\n").map((line, index) => {
                  const regex = /{([^}]+)}/g;
                  let match;
                  let parts = [];
                  let lastIndex = 0;
                  while ((match = regex.exec(line)) !== null) {
                    // Push text up to the match
                    if (match.index !== lastIndex) {
                      parts.push(line.substring(lastIndex, match.index));
                    }
                    // Push div with matched text
                    if (chat.message[match[1]]) {
                      parts.push(
                        <span className="my-1 rounded-md bg-indigo-100">
                          {chat.message[match[1]]}
                        </span>
                      );
                    }

                    // Update last index
                    lastIndex = regex.lastIndex;
                  }
                  // Push text after the last match
                  if (lastIndex !== line.length) {
                    parts.push(line.substring(lastIndex));
                  }
                  return <p>{parts}</p>;
                })
              : chat.message[chat.chatKey]}
          </span>
        </div>
      )}
    </div>
  );
}
