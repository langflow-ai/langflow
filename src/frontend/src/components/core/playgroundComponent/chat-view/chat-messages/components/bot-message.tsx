import { memo, useState } from "react";
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
import { useMessageDuration } from "../hooks/use-message-duration";
import { useStreamingMessage } from "../hooks/use-streaming-message";
import { useToolDurations } from "../hooks/use-tool-durations";
import {
  getContentBlockLoadingState,
  getContentBlockState,
} from "../utils/content-blocks";
import { convertFiles } from "../utils/convert-files";
import { formatSeconds, formatTime } from "../utils/format";
import EditMessageField from "./edit-message-field";
import { EditMessageButton } from "./message-options";

export const BotMessage = memo(
  ({ chat, lastMessage, updateChat, playgroundPage }: chatMessagePropsType) => {
    const setErrorData = useAlertStore((state) => state.setErrorData);
    const [editMessage, setEditMessage] = useState(false);
    const isBuilding = useFlowStore((state) => state.isBuilding);
    const buildStartTime = useFlowStore((state) => state.buildStartTime);
    const buildDuration = useFlowStore((state) => state.buildDuration);
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

    const { displayTime: liveDisplayTime } = useMessageDuration({
      lastMessage,
      isBuilding,
      buildStartTime,
      buildDuration,
    });

    // Prefer persisted duration (frozen value) over live timer
    // This ensures nested agent segments show their own duration after reset
    const persistedDuration = chat.properties?.build_duration;
    const displayTime =
      typeof persistedDuration === "number" && persistedDuration > 0
        ? persistedDuration
        : liveDisplayTime;

    // Use shared hook for tool duration tracking
    const { totalToolDuration } = useToolDurations(
      chat.content_blocks,
      thinkingActive,
    );

    // Check if message has tools
    const messageHasTools = Boolean(
      chat.content_blocks?.some((block) =>
        block.contents.some((content) => content.type === "tool_use"),
      ),
    );

    // The total tool duration green ms ALWAYS shows the sum of backend tool durations when tools exist
    // It will be 0 until backend provides durations, then show the sum
    // For messages without tools, it shows the same as displayTime
    const greenMsTime = messageHasTools ? totalToolDuration : displayTime;

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
            <div className="flex w-full flex-col gap-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                {!thinkingActive && displayTime > 0 && (
                  <ForwardedIconComponent
                    name="Check"
                    className="h-4 w-4 text-emerald-400"
                  />
                )}
                <span className="w-full flex justify-between">
                  {thinkingActive && displayTime > 0 ? (
                    <>
                      <span>Running... {formatSeconds(displayTime)}</span>
                      {messageHasTools && (
                        <span className="text-emerald-500">
                          {formatTime(greenMsTime, true)}
                        </span>
                      )}
                    </>
                  ) : !thinkingActive && displayTime > 0 ? (
                    <>
                      <span className="text-muted-foreground">
                        Finished in {formatSeconds(displayTime)}
                      </span>
                      {messageHasTools && greenMsTime > 0 && (
                        <span className="text-emerald-500">
                          {formatTime(greenMsTime, true)}
                        </span>
                      )}
                    </>
                  ) : null}
                </span>
              </div>

              {/* Show content blocks if they exist OR if we're building the last message (to show tools immediately when user sends message) */}
              {((chat.content_blocks && chat.content_blocks.length > 0) ||
                (isBuilding && lastMessage)) && (
                <ContentBlockDisplay
                  playgroundPage={playgroundPage}
                  contentBlocks={chat.content_blocks || []}
                  isLoading={getContentBlockLoadingState(
                    chat,
                    isBuilding,
                    lastMessage,
                  )}
                  state={getContentBlockState(chat, isBuilding, lastMessage)}
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
