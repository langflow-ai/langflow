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
import { User2, MessageSquare } from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../../../components/ui/accordion";
import { Badge } from "../../../components/ui/badge";

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
  return (
    <div
      className={classNames(
        "flex w-full px-2 py-6 pl-4 pr-9",
        chat.isSend ? " bg-border" : " "
      )}
    >
      <div className={classNames("mb-3 ml-3 mr-6 mt-1 ")}>
        {!chat.isSend ? (
          <div className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-md bg-[#afe6ef] p-5 text-2xl ">
            🤖
          </div>
        ) : (
          <div className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-md bg-[#aface9] p-5 text-2xl ">
            👨‍💻
          </div>
        )}
      </div>
      {!chat.isSend ? (
        <div className="flex w-full items-center text-start">
          <div className="relative inline-block w-full text-start text-sm font-normal text-primary">
            {hidden && chat.thought && chat.thought !== "" && (
              <div
                onClick={() => setHidden((prev) => !prev)}
                className="absolute -left-2 -top-1 cursor-pointer"
              >
                <MessageSquare className="h-5 w-5 animate-bounce dark:text-white" />
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
                    className="markdown prose max-w-full text-primary dark:prose-invert"
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
        <div className="flex w-full items-center">
          <div className="inline-block text-start">
            <span className=" break-all text-primary">
              <Accordion type="single" collapsible className="mb-2 flex">
                <AccordionItem
                  className=" rounded-md border border-ring/60 bg-muted px-4"
                  value="prompt"
                >
                  <AccordionTrigger className="gap-4 text-base font-semibold">
                    Initial Prompt
                  </AccordionTrigger>
                  <AccordionContent className="max-h-96 overflow-auto break-all p-2">
                    {
                      // Make all the variables that are inside curly braces bold
                      template.split("\n").map((line, index) => {
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
                    }
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
              <span className="prose text-primary dark:prose-invert">
                {chat.message[chat.chatKey]}
              </span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
