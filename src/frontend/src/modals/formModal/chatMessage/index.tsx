import Convert from "ansi-to-html";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import MaleTechnology from "../../../assets/male-technologist.png";
import Robot from "../../../assets/robot.png";
import SanitizedHTMLWrapper from "../../../components/SanitizedHTMLWrapper";
import CodeTabsComponent from "../../../components/codeTabsComponent";
import IconComponent from "../../../components/genericIconComponent";
import { chatMessagePropsType } from "../../../types/components";
import { classNames } from "../../../utils/utils";
import FileCard from "../fileComponent";

export default function ChatMessage({
  chat,
  lockChat,
  lastMessage,
}: chatMessagePropsType): JSX.Element {
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
                onClick={(): void => setHidden((prev) => !prev)}
                className="form-modal-chat-icon-div"
              >
                <IconComponent
                  name="MessageSquare"
                  className="form-modal-chat-icon"
                />
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
                  {chat.message.toString() === "" && lockChat ? (
                    <IconComponent
                      name="MoreHorizontal"
                      className="h-8 w-8 animate-pulse"
                    />
                  ) : (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeMathjax]}
                      className="markdown prose min-w-full text-primary word-break-break-word
                      dark:prose-invert"
                      components={{
                        pre({ node, ...props }) {
                          return <>{props.children}</>;
                        },
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

                          const match = /language-(\w+)/.exec(className || "");

                          return !inline ? (
                            <CodeTabsComponent
                              isMessage
                              tabs={[
                                {
                                  name: (match && match[1]) || "",
                                  mode: (match && match[1]) || "",
                                  image:
                                    "https://curl.se/logo/curl-symbol-transparent.png",
                                  language: (match && match[1]) || "",
                                  code: String(children).replace(/\n$/, ""),
                                },
                              ]}
                              activeTab={"0"}
                              setActiveTab={() => {}}
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
                <IconComponent
                  name="ChevronDown"
                  className={
                    "h-3 w-3 transition-all " + (promptOpen ? "rotate-180" : "")
                  }
                />
              </button>
              <span className="prose text-primary word-break-break-word dark:prose-invert">
                {promptOpen
                  ? template?.split("\n")?.map((line, index) => {
                      const regex = /{([^}]+)}/g;
                      let match;
                      let parts: Array<JSX.Element | string> = [];
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
