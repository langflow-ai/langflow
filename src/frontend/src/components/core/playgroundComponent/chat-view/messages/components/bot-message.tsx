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
              style={
                chat.properties?.background_color
                  ? { backgroundColor: chat.properties.background_color }
                  : {}
              }
            >
              <div className="flex h-5 w-5 items-center justify-center">
                {chat.properties?.icon ? (
                  isEmoji ? (
                    <span>{chat.properties.icon}</span>
                  ) : (
                    <ForwardedIconComponent name={chat.properties.icon} />
                  )
                ) : (
                  <LangflowLogo className="h-4 w-4 text-black" />
                )}
              </div>
            </div>

            {/* Content */}
            <div className="flex w-[94%] flex-col gap-2">
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
                  onEdit={
                    playgroundPage ? undefined : () => setEditMessage(true)
                  }
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
