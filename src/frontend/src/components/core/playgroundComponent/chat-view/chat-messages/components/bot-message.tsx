import { memo, useEffect, useMemo, useRef, useState } from "react";
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
import { useToolDurations } from "../hooks/use-tool-durations";
import { convertFiles } from "../utils/convert-files";
import EditMessageField from "./edit-message-field";
import { EditMessageButton } from "./message-options";

export const BotMessage = memo(
  ({ chat, lastMessage, updateChat, playgroundPage }: chatMessagePropsType) => {
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

    // Per-message duration tracking
    const [elapsedTime, setElapsedTime] = useState(0);
    const frozenDurationRef = useRef<number | null>(null);
    const messageStartTimeRef = useRef<number | null>(null);
    const chatIdRef = useRef(chat.id);

    // Use shared hook for tool duration tracking
    const { totalToolDuration, allToolsCompleted } = useToolDurations(
      chat.content_blocks,
      thinkingActive,
    );

    // Consolidated effect: handle reset, start, stop, and freeze logic
    useEffect(() => {
      // Reset when chat.id changes
      if (chatIdRef.current !== chat.id) {
        frozenDurationRef.current = null;
        messageStartTimeRef.current = null;
        setElapsedTime(0);
        chatIdRef.current = chat.id;
      }

      const isActive = lastMessage && isBuilding;
      const hasStartTime = messageStartTimeRef.current !== null;
      const isFrozen = frozenDurationRef.current !== null;

      // Start timer when message becomes active
      if (isActive && !hasStartTime && !isFrozen) {
        messageStartTimeRef.current = Date.now();
        setElapsedTime(0);
      }

      // Freeze when message becomes inactive (no longer last message) or building stops
      if (hasStartTime && !isFrozen) {
        if (!isActive) {
          // Message is no longer active (either not last message or not building)
          const finalDuration = Date.now() - messageStartTimeRef.current!;
          if (finalDuration > 0) {
            frozenDurationRef.current = finalDuration;
            setElapsedTime(finalDuration);
          }
        } else if (!isBuilding && lastMessage) {
          // Building stopped but this is still the last message
          const finalDuration = Date.now() - messageStartTimeRef.current!;
          if (finalDuration > 0) {
            frozenDurationRef.current = finalDuration;
            setElapsedTime(finalDuration);
          }
        }
      }
    }, [chat.id, lastMessage, isBuilding]);

    // Live timer: only update when actively building
    useEffect(() => {
      const isActive = lastMessage && isBuilding;

      // Immediately stop timer if not active or already frozen
      if (
        !isActive ||
        !messageStartTimeRef.current ||
        frozenDurationRef.current !== null
      ) {
        // If we have a start time but are no longer active, freeze immediately
        if (
          messageStartTimeRef.current &&
          !isActive &&
          frozenDurationRef.current === null
        ) {
          const finalDuration = Date.now() - messageStartTimeRef.current;
          if (finalDuration > 0) {
            frozenDurationRef.current = finalDuration;
            setElapsedTime(finalDuration);
          }
        }
        return;
      }

      const interval = setInterval(() => {
        // Double-check we're still active before updating
        if (
          lastMessage &&
          isBuilding &&
          messageStartTimeRef.current &&
          frozenDurationRef.current === null
        ) {
          setElapsedTime(Date.now() - messageStartTimeRef.current);
        }
      }, 100);

      return () => clearInterval(interval);
    }, [lastMessage, isBuilding]);

    const formatTime = (ms: number, showMsOnly: boolean = false) => {
      if (showMsOnly) {
        return `${Math.round(ms)}ms`;
      }
      if (ms < 1000) return `${Math.round(ms)}ms`;
      const seconds = ms / 1000;
      if (seconds < 60) return `${seconds.toFixed(1)}s`;
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = seconds % 60;
      return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
    };

    // Check if message has tools
    const hasTools = Boolean(
      chat.content_blocks?.some((block) =>
        block.contents.some((content) => content.type === "tool_use"),
      ),
    );

    // For messages with tools:
    // - Seconds display: use total thinking time (message timer) to show full duration
    // - Green ms: ALWAYS use sum of tool durations (only tool execution time)
    // For messages without tools: both use the message timer
    const displayTime =
      frozenDurationRef.current !== null
        ? frozenDurationRef.current
        : elapsedTime;

    // The green ms ALWAYS shows the sum of backend tool durations when tools exist
    // It will be 0 until backend provides durations, then show the sum
    // For messages without tools, it shows the same as displayTime
    const greenMsTime = hasTools ? totalToolDuration : displayTime;

    // Show thinking/thought message if:
    // 1. Actively thinking (isBuilding && lastMessage), OR
    // 2. We have a duration to display (frozen or elapsed) OR
    // 3. The message has tools (even if duration is 0 initially)
    const shouldShowThinkingMessage =
      thinkingActive || displayTime > 0 || hasTools;

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
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <ForwardedIconComponent
                  name="Brain"
                  className={cn(
                    "h-4 w-4",
                    thinkingActive
                      ? "text-primary animate-pulse"
                      : "text-muted-foreground",
                  )}
                />
                <span className="w-full flex justify-between">
                  {thinkingActive ? (
                    <>
                      <span>
                        Thinking for {(displayTime / 1000).toFixed(1)}s
                      </span>
                      {hasTools && (
                        <span className="text-emerald-500">
                          {formatTime(greenMsTime, true)}
                        </span>
                      )}
                    </>
                  ) : (
                    <>
                      <span className="text-muted-foreground">
                        Thought for {(displayTime / 1000).toFixed(1)}s
                      </span>
                      {hasTools && greenMsTime > 0 && (
                        <span className="text-emerald-500">
                          {formatTime(greenMsTime, true)}
                        </span>
                      )}
                    </>
                  )}
                </span>
              </div>

              {/* Show content blocks if they exist OR if we're building the last message (to show tools immediately when user sends message) */}
              {((chat.content_blocks && chat.content_blocks.length > 0) ||
                (isBuilding && lastMessage)) && (
                <ContentBlockDisplay
                  playgroundPage={playgroundPage}
                  contentBlocks={chat.content_blocks || []}
                  isLoading={
                    isBuilding &&
                    lastMessage &&
                    (!chat.content_blocks ||
                      chat.content_blocks.length === 0 ||
                      chat.properties?.state === "partial")
                  }
                  state={
                    chat.properties?.state ||
                    (isBuilding && lastMessage ? "partial" : undefined)
                  }
                  chatId={chat.id}
                  hideHeader={true}
                />
              )}

              <div className="flex w-full items-start gap-3">
                {(thinkingActive || displayTime > 0 || chatMessage !== "") && (
                  <div
                    className="relative hidden h-6 w-6 flex-shrink-0 items-center justify-center overflow-hidden rounded bg-white text-2xl @[45rem]/chat-panel:!flex border-0"
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
