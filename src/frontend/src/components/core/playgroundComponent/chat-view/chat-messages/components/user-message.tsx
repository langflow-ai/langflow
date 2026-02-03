import { memo, useState } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { EMPTY_INPUT_SEND_MESSAGE } from "@/constants/constants";
import { useUpdateMessage } from "@/controllers/API/queries/messages";
import { CustomProfileIcon } from "@/customization/components/custom-profile-icon";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { chatMessagePropsType } from "@/types/components";
import { cn } from "@/utils/utils";
import FilePreviewDisplay from "../../utils/file-preview-display";
import { convertFiles } from "../utils/convert-files";
import EditMessageField from "./edit-message-field";
import { EditMessageButton } from "./message-options";

export const UserMessage = memo(
  ({ chat, lastMessage, updateChat, playgroundPage }: chatMessagePropsType) => {
    const setErrorData = useAlertStore((state) => state.setErrorData);
    const [editMessage, setEditMessage] = useState(false);
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
    const hasFiles = chat.files && chat.files.length > 0;
    const { mutate: updateMessageMutation } = useUpdateMessage();

    const handleEditMessage = (message: string) => {
      updateMessageMutation(
        {
          message: {
            id: chat.id,
            files: convertFiles(chat.files),
            sender_name: chat.sender_name ?? "User",
            text: message,
            sender: "User",
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
            sender_name: chat.sender_name ?? "User",
            text: chat.message.toString(),
            sender: "User",
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
              "group relative flex w-full gap-4 rounded-md p-2 bg-muted @[45rem]/chat-panel:bg-transparent @[45rem]/chat-panel:p-2",
              editMessage ? "" : "hover:bg-muted",
            )}
          >
            {/* Avatar */}
            <div
              className="relative hidden h-6 w-6 items-center justify-center overflow-hidden rounded border border-border text-2xl hover-border-input @[45rem]/chat-panel:!flex border-0"
              style={
                chat.properties?.background_color
                  ? { backgroundColor: chat.properties.background_color }
                  : {}
              }
            >
              <div className="flex h-full w-full items-center justify-center">
                {chat.properties?.icon ? (
                  isEmoji ? (
                    <div>{chat.properties.icon}</div>
                  ) : (
                    <ForwardedIconComponent name={chat.properties.icon} />
                  )
                ) : (
                  <div className="h-full w-full [&>img]:h-full [&>img]:w-full [&>img]:object-cover">
                    <CustomProfileIcon />
                  </div>
                )}
              </div>
            </div>

            {/* Content */}
            <div className="flex w-[94%] flex-col gap-2">
              <div className="form-modal-chat-text-position flex-grow">
                <div className="flex w-full flex-col">
                  {editMessage ? (
                    <EditMessageField
                      key={`edit-message-${chat.id}`}
                      message={decodedMessage}
                      onEdit={handleEditMessage}
                      onCancel={() => setEditMessage(false)}
                    />
                  ) : (
                    <>
                      {/* Only show text section if there's content or no files */}
                      {(!isEmpty || !hasFiles) && (
                        <div
                          className={cn(
                            "w-full items-baseline whitespace-pre-wrap break-words text-sm font-normal",
                            isEmpty ? "text-muted-foreground" : "text-primary",
                          )}
                          data-testid={`chat-message-${chat.sender_name}-${chatMessage}`}
                        >
                          {isEmpty ? EMPTY_INPUT_SEND_MESSAGE : decodedMessage}
                          {editedFlag}
                        </div>
                      )}
                    </>
                  )}
                  {chat.files && chat.files.length > 0 && (
                    <div className="mt-2 flex w-full items-center gap-4 overflow-auto">
                      {chat.files.map((file, index) => (
                        <FilePreviewDisplay
                          key={index}
                          file={file}
                          variant="compact"
                          showDelete={false}
                        />
                      ))}
                    </div>
                  )}
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
                  isBotMessage={false}
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
