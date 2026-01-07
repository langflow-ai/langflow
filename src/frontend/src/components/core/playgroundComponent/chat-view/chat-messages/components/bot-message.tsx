import { memo, useCallback, useRef, useState } from "react";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import IconComponent, {
  ForwardedIconComponent,
} from "@/components/common/genericIconComponent";
import { ContentBlockDisplay } from "@/components/core/chatComponents/ContentBlockDisplay";
import { useUpdateMessage } from "@/controllers/API/queries/messages";
import { CustomMarkdownField } from "@/customization/components/custom-markdown-field";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { chatMessagePropsType } from "@/types/components";
import { cn } from "@/utils/utils";
import { useTypingEffect } from "../hooks/use-typing-effect";
import { convertFiles } from "../utils/convert-files";
import EditMessageField from "./edit-message-field";
import { EditMessageButton } from "./message-options";

export const BotMessage = memo(
  ({
    chat,
    lastMessage,
    updateChat,
    playgroundPage,
    isThinking,
    thinkingDuration,
  }: chatMessagePropsType) => {
    const setErrorData = useAlertStore((state) => state.setErrorData);
    const [editMessage, setEditMessage] = useState(false);
    const isBuilding = useFlowStore((state) => state.isBuilding);
    const flow_id = useFlowsManagerStore((state) => state.currentFlowId);
    const awaitingBotResponse = useUtilityStore(
      (state) => state.awaitingBotResponse,
    );
    const setAwaitingBotResponse = useUtilityStore(
      (state) => state.setAwaitingBotResponse,
    );

    const isAudioMessage = chat.category === "audio";
    const chatMessage = chat.message ? chat.message.toString() : "";
    let decodedMessage = chatMessage ?? "";
    try {
      decodedMessage = decodeURIComponent(chatMessage);
    } catch (_e) {
      // ignore decode errors
    }

    const isEmpty = decodedMessage?.trim() === "";

    // Capture at mount time whether this message should animate
    // This is true if we were awaiting a bot response when this message appeared
    const willAnimateRef = useRef(awaitingBotResponse && lastMessage);

    // Can start typing when: build is done + has content
    const canStart = !isBuilding && decodedMessage !== "";

    const handleTypingComplete = useCallback(() => {
      setAwaitingBotResponse(false);
    }, [setAwaitingBotResponse]);

    const { displayedText, isTyping } = useTypingEffect({
      text: decodedMessage,
      willAnimate: willAnimateRef.current,
      canStart,
      speed: 3,
      interval: 30,
      onComplete: handleTypingComplete,
    });
    const { mutate: updateMessageMutation } = useUpdateMessage();

    const handleEditMessage = (message: string) => {
      updateMessageMutation(
        {
          message: {
            id: chat.id,
            files: convertFiles(chat.files),
            sender_name: chat.sender_name ?? "AI",
            text: message,
            sender: "Machine",
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
            sender: "Machine",
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

    const isEmoji = chat.properties?.icon?.match(
      /[\u2600-\u27BF\uD83C-\uDBFF\uDC00-\uDFFF]/,
    );

    const thinkingActive = Boolean(isThinking && lastMessage);

    const formatTime = (ms: number) => {
      const seconds = ms / 1000;
      if (seconds < 60) return `${seconds.toFixed(1)}s`;
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = seconds % 60;
      return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
    };

    const stepsTotalDuration = chat.content_blocks
      ? chat.content_blocks.reduce((blockAcc, block) => {
          return (
            blockAcc +
            block.contents.reduce(
              (contentAcc, content) => contentAcc + (content.duration || 0),
              0,
            )
          );
        }, 0)
      : 0;

    const displayTime =
      stepsTotalDuration > 0 ? stepsTotalDuration : (thinkingDuration ?? 0);

    return (
      <>
        <div className="w-full py-4 word-break-break-word">
          <div
            className={cn(
              "group relative flex w-full flex-col gap-3 rounded-md p-2",
              editMessage ? "" : "hover:bg-muted",
            )}
          >
            {/* Content: thinking (paragraph) -> steps dropdown -> answer with bot avatar */}
            <div className="flex w-full flex-col gap-2">
              {(thinkingActive || displayTime > 0) && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <ForwardedIconComponent
                    name="Brain"
                    className="h-4 w-4 text-primary"
                  />
                  <span>
                    {thinkingActive ? "Thinking for " : "Thought for "}
                    <span className="text-emerald-500">
                      {formatTime(displayTime)}
                    </span>
                  </span>
                </div>
              )}

              {chat.content_blocks && chat.content_blocks.length > 0 && (
                <ContentBlockDisplay
                  playgroundPage={playgroundPage}
                  contentBlocks={chat.content_blocks}
                  isLoading={
                    chat.properties?.state === "partial" &&
                    isBuilding &&
                    lastMessage
                  }
                  state={chat.properties?.state}
                  chatId={chat.id}
                  hideHeader={true}
                />
              )}

              <div className="flex w-full items-start gap-3">
                {(thinkingActive ||
                  displayTime > 0 ||
                  chatMessage !== "" ||
                  isTyping) && (
                  <div
                    className="relative hidden h-8 w-8 flex-shrink-0 items-center justify-center overflow-hidden rounded bg-white text-2xl min-[45rem]:flex mdd:flex"
                    style={
                      chat.properties?.background_color
                        ? { backgroundColor: chat.properties.background_color }
                        : {}
                    }
                  >
                    <div className="flex h-5 w-5 items-center justify-center">
                      <LangflowLogo className="h-4 w-4 text-black" />
                    </div>
                  </div>
                )}

                <div className="form-modal-chat-text-position flex-grow">
                  <div className="form-modal-chat-text">
                    <div className="flex w-full flex-col">
                      <div
                        className="flex w-full flex-col dark:text-white"
                        data-testid="div-chat-message"
                      >
                        <div
                          data-testid={`chat-message-${chat.sender_name}-${chatMessage}`}
                          className="flex w-full flex-col"
                        >
                          {chatMessage === "" && isBuilding && lastMessage ? (
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
                                  onEdit={handleEditMessage}
                                  onCancel={() => setEditMessage(false)}
                                />
                              ) : (
                                <>
                                  <CustomMarkdownField
                                    isAudioMessage={isAudioMessage}
                                    chat={chat}
                                    isEmpty={isEmpty && !isTyping}
                                    chatMessage={displayedText}
                                    editedFlag={!isTyping ? editedFlag : null}
                                  />
                                  {isTyping && (
                                    <span className="inline-block w-1 h-4 bg-foreground animate-pulse ml-0.5 align-middle" />
                                  )}
                                </>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Actions */}
            {!editMessage && (
              <div className="invisible absolute -top-4 right-0 group-hover:visible">
                <EditMessageButton
                  onCopy={() => navigator.clipboard.writeText(chatMessage)}
                  onEdit={() => setEditMessage(true)}
                  className="h-fit group-hover:visible"
                  isBotMessage={true}
                  onEvaluate={handleEvaluateAnswer}
                  evaluation={chat.properties?.positive_feedback}
                  isAudioMessage={isAudioMessage}
                />
              </div>
            )}
          </div>
        </div>
        <div id={lastMessage ? "last-chat-message" : undefined} />
      </>
    );
  },
);
