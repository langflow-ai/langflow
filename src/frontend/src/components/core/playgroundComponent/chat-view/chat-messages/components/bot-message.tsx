import { memo, useEffect, useRef, useState } from "react";
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
import type { chatMessagePropsType } from "@/types/components";
import { cn } from "@/utils/utils";
import { useStreamingMessage } from "../hooks/use-streaming-message";
import { useThinkingDurationStore } from "../hooks/use-thinking-duration";
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

    const isAudioMessage = chat.category === "audio";

    const { chatMessage: decodedMessage, isStreaming } = useStreamingMessage({
      chat,
      isBuilding,
      updateChat,
    });

    const isEmpty = decodedMessage?.trim() === "";
    const chatMessage = chat.message ? chat.message.toString() : "";
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
            updateChat?.(chat, message);
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

    const thinkingActive = Boolean(isBuilding && lastMessage);
    const { startTime } = useThinkingDurationStore();
    const [elapsedTime, setElapsedTime] = useState(0);
    const lastElapsedTimeRef = useRef(0);

    // Live timer while building
    useEffect(() => {
      if (!isBuilding || !startTime) {
        // When building stops, preserve the last elapsed time
        if (!isBuilding && lastElapsedTimeRef.current > 0) {
          // Keep the last elapsed time for "Thought for" display
        }
        return;
      }

      const updateElapsed = () => {
        const start = useThinkingDurationStore.getState().startTime;
        if (start) {
          const elapsed = Date.now() - start;
          setElapsedTime(elapsed);
          lastElapsedTimeRef.current = elapsed;
        }
      };

      updateElapsed();

      const interval = setInterval(updateElapsed, 100);

      return () => clearInterval(interval);
    }, [isBuilding, startTime]);

    const formatTime = (ms: number) => {
      if (ms < 1000) return `${Math.round(ms)}ms`;
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

    // Use real-time elapsed time when thinking, otherwise use steps duration, thinking duration, or preserved elapsedTime
    // For the last message that just finished building, use the preserved elapsedTime if available
    const displayTime = thinkingActive
      ? elapsedTime
      : stepsTotalDuration > 0
        ? stepsTotalDuration
        : (thinkingDuration ?? 0) ||
          (lastMessage && lastElapsedTimeRef.current > 0
            ? lastElapsedTimeRef.current
            : 0);

    // Show thinking/thought message if:
    // 1. Actively thinking (isBuilding && lastMessage), OR
    // 2. We have a duration to display (from thinkingDuration, stepsTotalDuration, or preserved elapsedTime)
    const shouldShowThinkingMessage = thinkingActive || displayTime > 0;

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
              {shouldShowThinkingMessage && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <ForwardedIconComponent
                    name="Brain"
                    className="h-4 w-4 text-primary"
                  />
                  <span className="w-full flex justify-between">
                    <span>
                      {thinkingActive ? "Thinking for" : "Thought for"}
                    </span>
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
                {(thinkingActive || displayTime > 0 || chatMessage !== "") && (
                  <div
                    className="relative hidden h-8 w-8 flex-shrink-0 items-center justify-center overflow-hidden rounded bg-white text-2xl @[45rem]/chat-panel:!flex"
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
                          {(chatMessage === "" || (isEmpty && !isStreaming)) &&
                          isBuilding &&
                          lastMessage ? (
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
                                    isEmpty={isEmpty && !isStreaming}
                                    chatMessage={decodedMessage}
                                    editedFlag={editedFlag}
                                  />
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
