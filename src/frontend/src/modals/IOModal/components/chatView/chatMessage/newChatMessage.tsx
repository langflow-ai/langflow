import { ProfileIcon } from "@/components/appHeaderComponent/components/ProfileIcon";
import ShadTooltip from "@/components/shadTooltipComponent";
import { useUpdateMessage } from "@/controllers/API/queries/messages";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import Convert from "ansi-to-html";
import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax";
import remarkGfm from "remark-gfm";
import MaleTechnology from "../../../../../assets/male-technologist.png";
import Robot from "../../../../../assets/robot.png";
import CodeTabsComponent from "../../../../../components/codeTabsComponent/ChatCodeTabComponent";
import IconComponent from "../../../../../components/genericIconComponent";
import SanitizedHTMLWrapper from "../../../../../components/sanitizedHTMLWrapper";
import {
  EMPTY_INPUT_SEND_MESSAGE,
  EMPTY_OUTPUT_SEND_MESSAGE,
} from "../../../../../constants/constants";
import useAlertStore from "../../../../../stores/alertStore";
import { chatMessagePropsType } from "../../../../../types/components";
import { cn } from "../../../../../utils/utils";
import { EditMessageButton } from "./components/editMessageButton/newMessageOptions";
import EditMessageField from "./components/editMessageField/newEditMessageField";
import FileCardWrapper from "./components/fileCardWrapper";

export default function ChatMessage({
  chat,
  lockChat,
  lastMessage,
  updateChat,
  setLockChat,
}: chatMessagePropsType): JSX.Element {
  const convert = new Convert({ newline: true });
  const [hidden, setHidden] = useState(true);
  const template = chat.template;
  const [promptOpen, setPromptOpen] = useState(false);
  const [streamUrl, setStreamUrl] = useState(chat.stream_url);
  const flow_id = useFlowsManagerStore((state) => state.currentFlowId);
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
    <span className="text-sm text-chat-trigger-disabled">(Edited)</span>
  ) : null;

  return (
    <>
      <div className="flex-max-width px-2 py-6 pl-32 pr-9">
        <div className={"mr-3 mt-1 flex w-11/12 pb-3"}>
          <div
            className={cn(
              "group relative flex w-full gap-4 rounded-md p-2 hover:bg-zinc-800",
              editMessage ? "bg-zinc-800" : "",
            )}
          >
            <div
              className={cn(
                "relative flex h-8 w-8 items-center justify-center overflow-hidden rounded-md p-5 text-2xl",
                !chat.isSend ? "bg-chat-bot-icon" : "bg-zinc-400",
              )}
            >
              {!chat.isSend ? (
                <img
                  src={Robot}
                  className="absolute scale-[60%]"
                  alt={"robot_image"}
                />
              ) : (
                <div className="absolute scale-[80%]">
                  <ProfileIcon />
                </div>
              )}
            </div>
            <div className="flex w-[94%] flex-col">
              <div>
                <div
                  className="max-w-full truncate pb-2 font-semibold"
                  data-testid={
                    "sender_name_" + chat.sender_name?.toLocaleLowerCase()
                  }
                >
                  {chat.sender_name}
                </div>
                {/* TODO: ADD MODEL RELATED NAME */}
              </div>
              {!chat.isSend ? (
                <div className="form-modal-chat-text-position min-w-96 flex-grow">
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
                        content={convert.toHtml(chat.thought)}
                        onClick={() => setHidden((prev) => !prev)}
                      />
                    )}
                    {chat.thought && chat.thought !== "" && !hidden && (
                      <br></br>
                    )}
                    <div className="flex w-full flex-col">
                      <div
                        className="flex w-full flex-col dark:text-white"
                        data-testid="div-chat-message"
                      >
                        <div
                          data-testid={
                            "chat-message-" +
                            chat.sender_name +
                            "-" +
                            chatMessage
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
                                  <div className="flex w-full gap-2">
                                    <Markdown
                                      remarkPlugins={[remarkGfm]}
                                      linkTarget="_blank"
                                      rehypePlugins={[rehypeMathjax]}
                                      className={cn(
                                        "markdown prose flex w-full max-w-full flex-col word-break-break-word dark:prose-invert",
                                        isEmpty
                                          ? "text-chat-trigger-disabled"
                                          : "text-primary",
                                      )}
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
                                                  <span className="form-modal-markdown-span">
                                                    ▍
                                                  </span>
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
                                  </div>
                                  {editedFlag}
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
                <div className="form-modal-chat-text-position min-w-96 flex-grow">
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
                          "prose word-break-break-word dark:prose-invert",
                          !isEmpty
                            ? "text-primary"
                            : "text-chat-trigger-disabled",
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
                            className={`flex w-full gap-2 whitespace-pre-wrap break-words ${
                              isEmpty
                                ? "text-chat-trigger-disabled"
                                : "text-primary"
                            }`}
                            data-testid={`chat-message-${chat.sender_name}-${chatMessage}`}
                          >
                            {isEmpty
                              ? EMPTY_INPUT_SEND_MESSAGE
                              : decodedMessage}
                          </div>
                          {editedFlag}
                        </>
                      )}
                      {chat.files && (
                        <div className="my-2 flex flex-col gap-5">
                          {chat.files.map((file, index) => {
                            return (
                              <FileCardWrapper index={index} path={file} />
                            );
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
      </div>
      <div id={lastMessage ? "last-chat-message" : undefined} />
    </>
  );
}
