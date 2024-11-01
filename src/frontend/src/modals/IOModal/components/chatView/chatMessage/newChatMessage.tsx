import { ProfileIcon } from "@/components/appHeaderComponent/components/ProfileIcon";
import { TextShimmer } from "@/components/ui/TextShimmer";
import { useUpdateMessage } from "@/controllers/API/queries/messages";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { ContentBlock, ErrorContent } from "@/types/chat";
import Convert from "ansi-to-html";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax";
import remarkGfm from "remark-gfm";
import Robot from "../../../../../assets/robot.png";
import CodeTabsComponent from "../../../../../components/codeTabsComponent/ChatCodeTabComponent";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../../components/genericIconComponent";
import SanitizedHTMLWrapper from "../../../../../components/sanitizedHTMLWrapper";
import {
  EMPTY_INPUT_SEND_MESSAGE,
  EMPTY_OUTPUT_SEND_MESSAGE,
} from "../../../../../constants/constants";
import useAlertStore from "../../../../../stores/alertStore";
import { chatMessagePropsType } from "../../../../../types/components";
import { cn } from "../../../../../utils/utils";
import LogoIcon from "./components/chatLogoIcon";
import { EditMessageButton } from "./components/editMessageButton/newMessageOptions";
import EditMessageField from "./components/editMessageField/newEditMessageField";
import FileCardWrapper from "./components/fileCardWrapper";

export default function ChatMessage({
  chat,
  lockChat,
  lastMessage,
  updateChat,
  setLockChat,
  closeChat,
}: chatMessagePropsType): JSX.Element {
  const convert = new Convert({ newline: true });
  const [hidden, setHidden] = useState(true);
  const template = chat.template;
  const [promptOpen, setPromptOpen] = useState(false);
  const [streamUrl, setStreamUrl] = useState(chat.stream_url);
  const flow_id = useFlowsManagerStore((state) => state.currentFlowId);
  const fitViewNode = useFlowStore((state) => state.fitViewNode);
  // We need to check if message is not undefined because
  // we need to run .toString() on it
  const [chatMessage, setChatMessage] = useState(
    chat.message ? chat.message.toString() : "",
  );
  const [isStreaming, setIsStreaming] = useState(false);
  const eventSource = useRef<EventSource | undefined>(undefined);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const chatMessageRef = useRef(chatMessage);
  const [editMessage, setEditMessage] = useState(false);
  const [showError, setShowError] = useState(false);

  useEffect(() => {
    const chatMessageString = chat.message ? chat.message.toString() : "";
    setChatMessage(chatMessageString);
  }, [chat]);
  const playgroundScrollBehaves = useUtilityStore(
    (state) => state.playgroundScrollBehaves,
  );
  const setPlaygroundScrollBehaves = useUtilityStore(
    (state) => state.setPlaygroundScrollBehaves,
  );
  // Sync ref with state
  useEffect(() => {
    chatMessageRef.current = chatMessage;
  }, [chatMessage]);

  // The idea now is that chat.stream_url MAY be a URL if we should stream the output of the chat
  // probably the message is empty when we have a stream_url
  // what we need is to update the chat_message with the SSE data
  const streamChunks = (url: string) => {
    setIsStreaming(true); // Streaming starts
    return new Promise<boolean>((resolve, reject) => {
      eventSource.current = new EventSource(url);
      eventSource.current.onmessage = (event) => {
        let parsedData = JSON.parse(event.data);
        if (parsedData.chunk) {
          setChatMessage((prev) => prev + parsedData.chunk);
        }
      };
      eventSource.current.onerror = (event: any) => {
        setIsStreaming(false);
        eventSource.current?.close();
        setStreamUrl(undefined);
        if (JSON.parse(event.data)?.error) {
          setErrorData({
            title: "Error on Streaming",
            list: [JSON.parse(event.data)?.error],
          });
        }
        updateChat(chat, chatMessageRef.current);
        reject(new Error("Streaming failed"));
      };
      eventSource.current.addEventListener("close", (event) => {
        setStreamUrl(undefined); // Update state to reflect the stream is closed
        eventSource.current?.close();
        setIsStreaming(false);
        resolve(true);
      });
    });
  };

  useEffect(() => {
    if (streamUrl && !isStreaming) {
      setLockChat(true);
      streamChunks(streamUrl)
        .then(() => {
          setLockChat(false);
          if (updateChat) {
            updateChat(chat, chatMessageRef.current);
          }
        })
        .catch((error) => {
          console.error(error);
          setLockChat(false);
        });
    }
  }, [streamUrl, chatMessage]);

  useEffect(() => {
    return () => {
      eventSource.current?.close();
    };
  }, []);

  useEffect(() => {
    const element = document.getElementById("last-chat-message");
    if (element) {
      if (playgroundScrollBehaves === "instant") {
        element.scrollIntoView({ behavior: playgroundScrollBehaves });
        setPlaygroundScrollBehaves("smooth");
      } else {
        setTimeout(() => {
          element.scrollIntoView({ behavior: playgroundScrollBehaves });
        }, 200);
      }
    }
  }, [lastMessage, chat]);

  useEffect(() => {
    if (chat.category === "error") {
      // Short delay before showing error to allow for loading animation
      const timer = setTimeout(() => {
        setShowError(true);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [chat.category]);

  let decodedMessage = chatMessage ?? "";
  try {
    decodedMessage = decodeURIComponent(chatMessage);
  } catch (e) {
    console.error(e);
  }
  const isEmpty = decodedMessage?.trim() === "";
  const { mutate: updateMessageMutation } = useUpdateMessage();

  const convertFiles = (
    files:
      | (
          | string
          | {
              path: string;
              type: string;
              name: string;
            }
        )[]
      | undefined,
  ) => {
    if (!files) return [];
    return files.map((file) => {
      if (typeof file === "string") {
        return file;
      }
      return file.path;
    });
  };

  const handleEditMessage = (message: string) => {
    updateMessageMutation(
      {
        message: {
          ...chat,
          files: convertFiles(chat.files),
          sender_name: chat.sender_name ?? "AI",
          text: message,
          sender: chat.isSend ? "User" : "Machine",
          flow_id,
          session_id: chat.session ?? "",
        },
        refetch: true,
      },
      {
        onSuccess: () => {
          updateChat(chat, message);
          setEditMessage(false);
        },
        onError: () => {
          setErrorData({
            title: "Error updating messages.",
          });
        },
      },
    );
  };
  const editedFlag = chat.edit ? (
    <div className="text-sm text-muted-foreground">(Edited)</div>
  ) : null;

  if (chat.category === "error") {
    const block = (chat.content_blocks?.[0] ?? {}) as ContentBlock;
    const errorContent = (block.content as ErrorContent) ?? {};
    return (
      <div className="w-5/6 max-w-[768px] py-4 word-break-break-word">
        <AnimatePresence mode="wait">
          {!showError && lastMessage ? (
            <motion.div
              key="loading"
              initial={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex w-full gap-4 rounded-md p-2"
            >
              <LogoIcon />
              <div className="flex items-center">
                <TextShimmer className="" duration={1}>
                  Flow running...
                </TextShimmer>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="error"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.3 }}
              className="flex w-full gap-4 rounded-md p-2"
            >
              <LogoIcon />
              <div className="w-full rounded-md border border-error-red-border bg-error-red p-4 text-[14px] text-foreground">
                <div className="mb-2 flex items-center gap-2">
                  <ForwardedIconComponent
                    className="h-[18px] w-[18px] text-destructive"
                    name="OctagonAlert"
                  />
                  <span className="">An error stopped your flow.</span>
                </div>
                <div className="mb-4">
                  <h3 className="pb-3 font-semibold">Error details:</h3>
                  <p className="pb-1">
                    Component:{" "}
                    <span
                      className={cn(
                        closeChat ? "cursor-pointer underline" : "",
                      )}
                      onClick={() => {
                        fitViewNode(chat.properties?.source?.id ?? "");
                        closeChat?.();
                      }}
                    >
                      {errorContent.component}
                    </span>
                  </p>
                  {errorContent.field && (
                    <p className="pb-1">Field: {errorContent.field}</p>
                  )}
                  {errorContent.reason && (
                    <span className="">
                      Reason:{" "}
                      <Markdown
                        linkTarget="_blank"
                        remarkPlugins={[remarkGfm]}
                        components={{
                          a: ({ node, ...props }) => {
                            return (
                              <a
                                href={props.href}
                                target="_blank"
                                className="underline"
                                rel="noopener noreferrer"
                              >
                                {props.children}
                              </a>
                            );
                          },
                        }}
                      >
                        {errorContent.reason}
                      </Markdown>
                    </span>
                  )}
                </div>
                {errorContent.solution && (
                  <div>
                    <h3 className="pb-3 font-semibold">Steps to fix:</h3>
                    <ol className="list-decimal pl-5">
                      <li>Check the component settings</li>
                      <li>Ensure all required fields are filled</li>
                      <li>Re-run your flow</li>
                    </ol>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  }

  return (
    <>
      <div className="w-5/6 max-w-[768px] py-4 word-break-break-word">
        <div
          className={cn(
            "group relative flex w-full gap-4 rounded-md p-2",
            editMessage ? "" : "hover:bg-muted",
          )}
        >
          <div
            className={cn(
              "relative flex h-[32px] w-[32px] items-center justify-center overflow-hidden rounded-md text-2xl",
              !chat.isSend
                ? "bg-muted"
                : "border border-border hover:border-input",
            )}
            style={
              chat.properties?.background_color
                ? { backgroundColor: chat.properties.background_color }
                : {}
            }
          >
            {!chat.isSend ? (
              <div className="flex h-[18px] w-[18px] items-center justify-center">
                {chat.properties?.icon ? (
                  chat.properties.icon.match(
                    /[\u2600-\u27BF\uD83C-\uDBFF\uDC00-\uDFFF]/,
                  ) ? (
                    <span className="">{chat.properties.icon}</span>
                  ) : (
                    <ForwardedIconComponent name={chat.properties.icon} />
                  )
                ) : (
                  <img
                    src={Robot}
                    className="absolute bottom-0 left-0 scale-[60%]"
                    alt={"robot_image"}
                  />
                )}
              </div>
            ) : (
              <div className="flex h-[18px] w-[18px] items-center justify-center">
                {chat.properties?.icon ? (
                  chat.properties.icon.match(
                    /[\u2600-\u27BF\uD83C-\uDBFF\uDC00-\uDFFF]/,
                  ) ? (
                    <div className="">{chat.properties.icon}</div>
                  ) : (
                    <ForwardedIconComponent name={chat.properties.icon} />
                  )
                ) : (
                  <ProfileIcon />
                )}
              </div>
            )}
          </div>
          <div className="flex w-[94%] flex-col">
            <div>
              <div
                className={cn(
                  "flex max-w-full items-baseline gap-3 truncate pb-2 text-[14px] font-semibold",
                )}
                style={
                  chat.properties?.text_color
                    ? { color: chat.properties.text_color }
                    : {}
                }
                data-testid={
                  "sender_name_" + chat.sender_name?.toLocaleLowerCase()
                }
              >
                {chat.sender_name}
                {chat.properties?.source && (
                  <div className="text-[13px] font-normal text-muted-foreground">
                    {chat.properties?.source.source}
                  </div>
                )}
              </div>
            </div>
            {!chat.isSend ? (
              <div className="form-modal-chat-text-position flex-grow">
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
                      className="form-modal-chat-thought"
                      content={convert.toHtml(chat.thought ?? "")}
                      onClick={() => setHidden((prev) => !prev)}
                    />
                  )}
                  {chat.thought && chat.thought !== "" && !hidden && <br></br>}
                  <div className="flex w-full flex-col">
                    <div
                      className="flex w-full flex-col dark:text-white"
                      data-testid="div-chat-message"
                    >
                      <div
                        data-testid={
                          "chat-message-" + chat.sender_name + "-" + chatMessage
                        }
                        className="flex w-full flex-col"
                      >
                        {chatMessage === "" && lockChat ? (
                          <IconComponent
                            name="MoreHorizontal"
                            className="h-8 w-8 animate-pulse"
                          />
                        ) : (
                          <div className="w-full">
                            {editMessage ? (
                              <EditMessageField
                                key={`edit-message-${chat.id}`}
                                message={decodedMessage}
                                onEdit={(message) => {
                                  handleEditMessage(message);
                                }}
                                onCancel={() => setEditMessage(false)}
                              />
                            ) : (
                              <>
                                <div className="w-full items-baseline gap-2">
                                  <Markdown
                                    remarkPlugins={[remarkGfm]}
                                    linkTarget="_blank"
                                    rehypePlugins={[rehypeMathjax]}
                                    className={cn(
                                      "markdown prose flex w-fit max-w-full flex-col items-baseline text-[14px] font-normal word-break-break-word dark:prose-invert",
                                      isEmpty
                                        ? "text-muted-foreground"
                                        : "text-primary",
                                    )}
                                    components={{
                                      p({ node, ...props }) {
                                        return (
                                          <span className="inline-block w-fit max-w-full">
                                            {props.children}
                                          </span>
                                        );
                                      },
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
                                        let content = children as string;
                                        if (
                                          Array.isArray(children) &&
                                          children.length === 1 &&
                                          typeof children[0] === "string"
                                        ) {
                                          content = children[0] as string;
                                        }
                                        if (typeof content === "string") {
                                          if (content.length) {
                                            if (content[0] === "▍") {
                                              return (
                                                <span className="form-modal-markdown-span"></span>
                                              );
                                            }
                                          }

                                          const match = /language-(\w+)/.exec(
                                            className || "",
                                          );

                                          return !inline ? (
                                            <CodeTabsComponent
                                              language={
                                                (match && match[1]) || ""
                                              }
                                              code={String(content).replace(
                                                /\n$/,
                                                "",
                                              )}
                                            />
                                          ) : (
                                            <code
                                              className={className}
                                              {...props}
                                            >
                                              {content}
                                            </code>
                                          );
                                        }
                                      },
                                    }}
                                  >
                                    {isEmpty && !chat.stream_url
                                      ? EMPTY_OUTPUT_SEND_MESSAGE
                                      : chatMessage}
                                  </Markdown>
                                  {editedFlag}
                                </div>
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="form-modal-chat-text-position flex-grow">
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
                        className={`h-3 w-3 transition-all ${promptOpen ? "rotate-180" : ""}`}
                      />
                    </button>
                    <span
                      className={cn(
                        "prose text-[14px] font-normal word-break-break-word dark:prose-invert",
                        !isEmpty ? "text-primary" : "text-muted-foreground",
                      )}
                    >
                      {promptOpen
                        ? template?.split("\n")?.map((line, index) => {
                            const regex = /{([^}]+)}/g;
                            let match;
                            let parts: Array<JSX.Element | string> = [];
                            let lastIndex = 0;
                            while ((match = regex.exec(line)) !== null) {
                              // Push text up to the match
                              if (match.index !== lastIndex) {
                                parts.push(
                                  line.substring(lastIndex, match.index),
                                );
                              }
                              // Push div with matched text
                              if (chat.message[match[1]]) {
                                parts.push(
                                  <span className="chat-message-highlight">
                                    {chat.message[match[1]]}
                                  </span>,
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
                        : isEmpty
                          ? EMPTY_INPUT_SEND_MESSAGE
                          : chatMessage}
                    </span>
                  </>
                ) : (
                  <div className="flex w-full flex-col">
                    {editMessage ? (
                      <EditMessageField
                        key={`edit-message-${chat.id}`}
                        message={decodedMessage}
                        onEdit={(message) => {
                          handleEditMessage(message);
                        }}
                        onCancel={() => setEditMessage(false)}
                      />
                    ) : (
                      <>
                        <div
                          className={`w-full items-baseline whitespace-pre-wrap break-words text-[14px] font-normal ${
                            isEmpty ? "text-muted-foreground" : "text-primary"
                          }`}
                          data-testid={`chat-message-${chat.sender_name}-${chatMessage}`}
                        >
                          {isEmpty ? EMPTY_INPUT_SEND_MESSAGE : decodedMessage}
                          {editedFlag}
                        </div>
                      </>
                    )}
                    {chat.files && (
                      <div className="my-2 flex flex-col gap-5">
                        {chat.files?.map((file, index) => {
                          return <FileCardWrapper index={index} path={file} />;
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
          {!editMessage && (
            <div className="invisible absolute -top-4 right-0 group-hover:visible">
              <div>
                <EditMessageButton
                  onCopy={() => {
                    navigator.clipboard.writeText(chatMessage);
                  }}
                  onDelete={() => {}}
                  onEdit={() => setEditMessage(true)}
                  className="h-fit group-hover:visible"
                />
              </div>
            </div>
          )}
        </div>
      </div>
      <div id={lastMessage ? "last-chat-message" : undefined} />
    </>
  );
}
