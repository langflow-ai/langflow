import Convert from "ansi-to-html";
import { ChevronDown } from "lucide-react";
import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import MaleTechnology from "../../../assets/male-technologist.png";
import Robot from "../../../assets/robot.png";
import SanitizedHTMLWrapper from "../../../components/SanitizedHTMLWrapper";
import { THOUGHTS_ICON } from "../../../constants";
import { ChatMessageType } from "../../../types/chat";
import { classNames } from "../../../utils";
import FileCard from "../fileComponent";
import { CodeBlock } from "./codeBlock";
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
  const template = chat.template;
  const [promptOpen, setPromptOpen] = useState(false);
  return (
    <div
      className={classNames("form-modal-chat-position", chat.isSend ? "" : " ")}
    >
      <div className={classNames("form-modal-chatbot-icon ")}>
        {!chat.isSend ? (
          <div className="form-modal-chat-image">
            <div className="form-modal-chat-bot-icon ">
              <img
                src={Robot}
                className="form-modal-chat-icon-img"
                alt="robot_image"
              />
            </div>
          </div>
        ) : (
          <div className="form-modal-chat-image">
            <div className="form-modal-chat-user-icon ">
              <img
                src={MaleTechnology}
                className="form-modal-chat-icon-img"
                alt="male_technology"
              />
            </div>
          </div>
        )}
      </div>
      {!chat.isSend ? (
        <div className="form-modal-chat-text-position">
          <div className="form-modal-chat-text">
            {hidden && chat.thought && chat.thought !== "" && (
              <div
                onClick={() => setHidden((prev) => !prev)}
                className="form-modal-chat-icon-div"
              >
                <THOUGHTS_ICON className="form-modal-chat-icon" />
              </div>
            )}
            {chat.thought && chat.thought !== "" && !hidden && (
              <SanitizedHTMLWrapper
                className=" form-modal-chat-thought"
                content={convert.toHtml(chat.thought)}
                onClick={() => setHidden((prev) => !prev)}
              />
            )}
            {chat.thought && chat.thought !== "" && !hidden && <br></br>}
            <div className="w-full">
              <div className="w-full dark:text-white">
                <div className="w-full">
                  {useMemo(
                    () => (
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm, remarkMath]}
                        rehypePlugins={[rehypeMathjax]}
                        className="markdown prose inline-block break-words text-primary
                     dark:prose-invert sm:max-w-[30vw] lg:max-w-[40vw] sm:w-[30vw] lg:w-[40vw]"
                        components={{
                          code: ({
                            node,
                            inline,
                            className,
                            children,
                            ...props
                          }) => {
                            if (children.length) {
                              if (children[0] === "▍") {
                                return (
                                  <span className="form-modal-markdown-span">
                                    ▍
                                  </span>
                                );
                              }

                              children[0] = (children[0] as string).replace(
                                "`▍`",
                                "▍"
                              );
                            }

                            const match = /language-(\w+)/.exec(
                              className || ""
                            );

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
                    ),
                    [chat.message, chat.message.toString()]
                  )}
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
          {template ? (
            <>
              <button
                className="form-modal-initial-prompt-btn"
                onClick={() => {
                  setPromptOpen((old) => !old);
                }}
              >
                Display Prompt
                <ChevronDown
                  className={
                    "h-3 w-3 transition-all " + (promptOpen ? "rotate-180" : "")
                  }
                />
              </button>
              <span className="prose inline-block break-words text-primary dark:prose-invert">
                {promptOpen
                  ? template?.split("\n")?.map((line, index) => {
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
                            <span className="chat-message-highlight">
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
            </>
          ) : (
            <span>{chat.message[chat.chatKey]}</span>
          )}
        </div>
      )}
    </div>
  );
}
