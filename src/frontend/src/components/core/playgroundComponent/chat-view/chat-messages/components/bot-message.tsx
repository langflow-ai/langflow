import { memo, useState } from "react";
import { useTranslation } from "react-i18next";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import IconComponent, {
  ForwardedIconComponent,
} from "@/components/common/genericIconComponent";
import MessageMetadata from "@/components/common/messageMetadataComponent";
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
import {
  getContentBlockLoadingState,
  getContentBlockState,
} from "../utils/content-blocks";
import { convertFiles } from "../utils/convert-files";
import { formatSeconds } from "../utils/format";
import EditMessageField from "./edit-message-field";
import { EditMessageButton } from "./message-options";

export const BotMessage = memo(
  ({ chat, lastMessage, updateChat, playgroundPage }: chatMessagePropsType) => {
    const { t } = useTranslation();
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
              title: t("errors.updatingMessages"),
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
              state: chat.properties?.state as
                | "complete"
                | "partial"
                | undefined,
              positive_feedback: evaluation,
            },
          },
        },
        {
          onError: () => {
            setErrorData({
              title: t("errors.updatingMessages"),
            });
          },
        },
      );
    };

    const editedFlag = chat.edit ? (
      <div className="mt-2 text-xs text-muted-foreground text-right">
        (Edited)
      </div>
    ) : null;

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

    // A message with token usage should still surface the MessageMetadata
    // pill even when no duration was recorded (e.g. v2 runs that didn't
    // emit ``build_duration``, historical messages restored from DB).
    // Without this the user would never see "X tokens" for those.
    const totalTokens = chat.properties?.usage?.total_tokens;
    const hasUsage = typeof totalTokens === "number" && totalTokens > 0;
    const showMetadata = displayTime > 0 || hasUsage;

    // The renderer is data-driven, but content_blocks shows up in two
    // shapes:
    //   - Legacy: an "Agent Steps" group wraps the tool calls (and the
    //     legacy agent also appends a flat TextContent at the top that
    //     duplicates Message.text). Render the group via the accordion
    //     and let CustomMarkdownField paint Message.text below — the
    //     historical "tools on top, text after" layout.
    //   - Interleaved (post agent-events rewiring): no group, just flat
    //     tool_use / citation / text items in producer order. Trust the
    //     content_blocks order and suppress the bubble body so text
    //     doesn't double-paint.
    // The signal is: a flat non-text block (tool_use, citation, …) with
    // no group present means the producer is making an ordering claim.
    const contentBlocks = chat.content_blocks ?? [];
    const hasGroup = contentBlocks.some((block) => block.type === "group");
    const hasFlatNonText = contentBlocks.some(
      (block) => block.type !== "group" && block.type !== "text",
    );
    const hasTextBlock = contentBlocks.some((block) => block.type === "text");
    const useContentBlockOrdering = !hasGroup && hasFlatNonText;
    // Suppress the bubble body only when the content blocks actually carry
    // the answer text. If a producer emits only flat tool_use / citation
    // items (no TextContent) and stuffs the answer into Message.text,
    // keep the bubble body so the assistant text isn't hidden.
    const showBubbleBody =
      !useContentBlockOrdering || editMessage || !hasTextBlock;
    // In legacy / pure-text mode, strip a top-level TextContent only when it
    // duplicates Message.text — those items would render above the grouped
    // accordion. A divergent text block (text !== Message.text) is kept so
    // it isn't silently dropped.
    const displayedContentBlocks = useContentBlockOrdering
      ? contentBlocks
      : contentBlocks.filter(
          (block) =>
            block.type !== "text" || block.text !== chat.message?.toString(),
        );

    return (
      <>
        <div className="w-full word-break-break-word mt-2">
          <div
            className={cn(
              "group relative flex w-full flex-col gap-3 rounded-md px-2 py-3",
              editMessage ? "" : "hover:bg-muted",
            )}
          >
            <div className="flex w-full items-start gap-3">
              {(thinkingActive || displayTime > 0 || chatMessage !== "") && (
                <div
                  className="relative hidden h-6 w-6 mt-[-1px] flex-shrink-0 items-center justify-center overflow-hidden rounded bg-white text-2xl @[45rem]/chat-panel:!flex border-0"
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

              <div className="flex w-full flex-col min-w-0">
                <span className="text-sm font-medium text-foreground mb-1">
                  {chat.sender_name ?? "AI"}
                </span>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  {!thinkingActive && displayTime > 0 && (
                    <ForwardedIconComponent
                      name="Check"
                      className="h-4 w-4 text-accent-emerald-foreground"
                    />
                  )}
                  <span className="w-full flex justify-between">
                    {thinkingActive && displayTime > 0 ? (
                      <span>
                        {t("chat.runningStatus")} {formatSeconds(displayTime)}
                      </span>
                    ) : !thinkingActive && showMetadata ? (
                      <>
                        {displayTime > 0 && (
                          <span className="text-muted-foreground">
                            {t("chat.finishedIn")}
                          </span>
                        )}
                        <MessageMetadata
                          duration={displayTime > 0 ? displayTime : undefined}
                          usage={chat.properties?.usage ?? undefined}
                          timestamp={chat.timestamp}
                        />
                      </>
                    ) : null}
                  </span>
                </div>

                {(displayedContentBlocks.length > 0 ||
                  (isBuilding && lastMessage)) && (
                  <ContentBlockDisplay
                    playgroundPage={playgroundPage}
                    contentBlocks={displayedContentBlocks}
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

                {showBubbleBody && (
                  <div className="form-modal-chat-text-position flex-grow mt-2">
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
                            {(chatMessage === "" ||
                              (isEmpty && !isStreaming)) &&
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
                )}
              </div>
            </div>

            {!editMessage && (
              <div className="invisible absolute bottom-full right-0 group-hover:visible">
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
