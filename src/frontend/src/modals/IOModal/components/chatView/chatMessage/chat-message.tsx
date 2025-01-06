import { ProfileIcon } from "@/components/core/appHeaderComponent/components/ProfileIcon";
import { ContentBlockDisplay } from "@/components/core/chatComponents/ContentBlockDisplay";
import { useUpdateMessage } from "@/controllers/API/queries/messages";
import { CustomProfileIcon } from "@/customization/components/custom-profile-icon";
import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { useUtilityStore } from "@/stores/utilityStore";
import Convert from "ansi-to-html";
import { useEffect, useRef, useState } from "react";
import Robot from "../../../../../assets/robot.png";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../../components/common/genericIconComponent";
import SanitizedHTMLWrapper from "../../../../../components/common/sanitizedHTMLWrapper";
import { EMPTY_INPUT_SEND_MESSAGE } from "../../../../../constants/constants";
import useTabVisibility from "../../../../../shared/hooks/use-tab-visibility";
import useAlertStore from "../../../../../stores/alertStore";
import { chatMessagePropsType } from "../../../../../types/components";
import { cn } from "../../../../../utils/utils";
import { ErrorView } from "./components/content-view";
import { MarkdownField } from "./components/edit-message";
import EditMessageField from "./components/edit-message-field";
import FileCardWrapper from "./components/file-card-wrapper";
import { EditMessageButton } from "./components/message-options";
import { convertFiles } from "./helpers/convert-files";

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

  const isTabHidden = useTabVisibility();

  useEffect(() => {
    const element = document.getElementById("last-chat-message");
    if (element && isTabHidden) {
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
    // console.error(e);
  }
  const isEmpty = decodedMessage?.trim() === "";
  const { mutate: updateMessageMutation } = useUpdateMessage();

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

  const handleEvaluateAnswer = (evaluation: boolean | null) => {
    updateMessageMutation(
      {
        message: {
          ...chat,
          files: convertFiles(chat.files),
          sender_name: chat.sender_name ?? "AI",
          text: chat.message.toString(),
          sender: chat.isSend ? "User" : "Machine",
          flow_id,
          session_id: chat.session ?? "",
          properties: {
            ...chat.properties,
            positive_feedback: evaluation,
          },
        },
        refetch: true,
      },
      {
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
    const blocks = chat.content_blocks ?? [];

    return (
      <ErrorView
        blocks={blocks}
        showError={showError}
        lastMessage={lastMessage}
        closeChat={closeChat}
        fitViewNode={fitViewNode}
        chat={chat}
      />
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
                ) : !ENABLE_DATASTAX_LANGFLOW ? (
                  <ProfileIcon />
                ) : (
                  <CustomProfileIcon />
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
            {chat.content_blocks && chat.content_blocks.length > 0 && (
              <ContentBlockDisplay
                contentBlocks={chat.content_blocks}
                isLoading={
                  chatMessage === "" &&
                  lockChat &&
                  chat.properties?.state === "partial"
                }
                state={chat.properties?.state}
                chatId={chat.id}
              />
            )}
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
                              <MarkdownField
                                chat={chat}
                                isEmpty={isEmpty}
                                chatMessage={chatMessage}
                                editedFlag={editedFlag}
                              />
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
                  isBotMessage={!chat.isSend}
                  onEvaluate={handleEvaluateAnswer}
                  evaluation={chat.properties?.positive_feedback}
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
