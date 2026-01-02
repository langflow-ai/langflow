import { memo, useCallback, useMemo, useState } from "react";
import LangflowLogo from "@/assets/LangflowLogo.svg?react";
import IconComponent, {
  ForwardedIconComponent,
} from "@/components/common/genericIconComponent";
import { ContentBlockDisplay } from "@/components/core/chatComponents/ContentBlockDisplay";
import EditMessageField from "@/components/core/playgroundComponent/chat-view/chat-messages/components/edit-message-field";
import { EditMessageButton } from "@/components/core/playgroundComponent/chat-view/chat-messages/components/message-options";
import { useUpdateMessage } from "@/controllers/API/queries/messages";
import { CustomMarkdownField } from "@/customization/components/custom-markdown-field";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { ContentBlock, JSONObject } from "@/types/chat";
import type { chatMessagePropsType } from "@/types/components";
import { cn } from "@/utils/utils";
import { convertFiles } from "../utils/convert-files";

export const BotMessage = memo(
  ({ chat, lastMessage, updateChat, playgroundPage }: chatMessagePropsType) => {
    const setErrorData = useAlertStore((state) => state.setErrorData);
    const [editMessage, setEditMessage] = useState(false);
    const isBuilding = useFlowStore((state) => state.isBuilding);
    const flow_id = useFlowsManagerStore((state) => state.currentFlowId);

    const isAudioMessage = chat.category === "audio";
    const chatMessage = chat.message ? chat.message.toString() : "";

    let decodedMessage = chatMessage ?? "";
    try {
      decodedMessage = decodeURIComponent(chatMessage);
    } catch (_e) {
      // ignore decode errors
    }

    const isEmpty = decodedMessage?.trim() === "";
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
            id: chat.id,
            files: convertFiles(chat.files),
            sender_name: chat.sender_name ?? "AI",
            text: chat.message.toString(),
            sender: "Machine",
            flow_id,
            session_id: chat.session ?? "",
            timestamp:
              chat.timestamp?.toString?.() ?? String(chat.timestamp ?? ""),
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

    const handleStartEdit = useCallback(() => setEditMessage(true), []);

    const editedFlag = chat.edit ? (
      <div className="text-sm text-muted-foreground">(Edited)</div>
    ) : null;

    const icon =
      typeof chat.properties?.icon === "string"
        ? chat.properties.icon
        : undefined;
    const isEmoji = icon
      ? icon.match(/[\u2600-\u27BF\uD83C-\uDBFF\uDC00-\uDFFF]/)
      : null;

    const backgroundColor =
      typeof chat.properties?.background_color === "string"
        ? chat.properties.background_color
        : undefined;
    const positiveFeedback =
      typeof chat.properties?.positive_feedback === "boolean" ||
      chat.properties?.positive_feedback === null
        ? chat.properties.positive_feedback
        : undefined;
    const state =
      typeof chat.properties?.state === "string"
        ? chat.properties.state
        : undefined;

    const isContentBlock = (
      block: ContentBlock | JSONObject,
    ): block is ContentBlock =>
      typeof (block as ContentBlock).title === "string" &&
      Array.isArray((block as ContentBlock).contents);

    const contentBlocks = useMemo(
      () =>
        Array.isArray(chat.content_blocks)
          ? chat.content_blocks.filter(isContentBlock)
          : [],
      [chat.content_blocks],
    );

    return (
      <>
        <div className="w-full py-4 word-break-break-word">
          <div
            className={cn(
              "group relative flex w-full gap-4 rounded-md p-2",
              editMessage ? "" : "hover:bg-muted",
            )}
          >
            {/* Avatar */}
            <div
              className="relative flex h-8 w-8 items-center justify-center overflow-hidden rounded bg-white text-2xl"
              style={backgroundColor ? { backgroundColor } : undefined}
            >
              <div className="flex h-5 w-5 items-center justify-center">
                {icon ? (
                  isEmoji ? (
                    <span>{icon}</span>
                  ) : (
                    <ForwardedIconComponent name={icon} />
                  )
                ) : (
                  <LangflowLogo className="h-4 w-4 text-black" />
                )}
              </div>
            </div>

            {/* Content */}
            <div className="flex w-[94%] flex-col gap-2">
              {contentBlocks.length > 0 && (
                <ContentBlockDisplay
                  playgroundPage={playgroundPage}
                  contentBlocks={contentBlocks}
                  isLoading={state === "partial" && isBuilding && lastMessage}
                  state={state}
                  chatId={chat.id}
                />
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
                          <div className="min-h-8 w-full">
                            {editMessage ? (
                              <EditMessageField
                                key={`edit-message-${chat.id}`}
                                message={decodedMessage}
                                onEdit={handleEditMessage}
                                onCancel={() => setEditMessage(false)}
                              />
                            ) : (
                              <CustomMarkdownField
                                isAudioMessage={isAudioMessage}
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
            </div>

            {/* Actions */}
            {!editMessage && (
              <div className="invisible absolute -top-4 right-0 group-hover:visible">
                <EditMessageButton
                  onCopy={() => navigator.clipboard.writeText(chatMessage)}
                  onEdit={handleStartEdit}
                  className="h-fit group-hover:visible"
                  isBotMessage={true}
                  onEvaluate={handleEvaluateAnswer}
                  evaluation={positiveFeedback}
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
