import { memo, useState } from "react";
import { ContentBlockDisplay } from "@/components/core/chatComponents/ContentBlockDisplay";
import { useUpdateMessage } from "@/controllers/API/queries/messages";
import { CustomMarkdownField } from "@/customization/components/custom-markdown-field";
import useFlowStore from "@/stores/flowStore";
import useAlertStore from "../../../../../../stores/alertStore";
import type { chatMessagePropsType } from "../../../../../../types/components";
import { cn } from "../../../../../../utils/utils";
import IconComponent from "../../../../../common/genericIconComponent";
import EditMessageField from "./components/edit-message-field";
import { EditMessageButton } from "./components/message-options";
import { convertFiles } from "./helpers/convert-files";

export const BotMessage = memo(
  ({ chat, lastMessage, updateChat, playgroundPage }: chatMessagePropsType) => {
    const setErrorData = useAlertStore((state) => state.setErrorData);
    const [editMessage, setEditMessage] = useState(false);
    const isBuilding = useFlowStore((state) => state.isBuilding);

    const isAudioMessage = chat.category === "audio";

    const isEmpty = chat.text?.trim() === "";
    const { mutate: updateMessageMutation } = useUpdateMessage();

    const handleEditMessage = (message: string) => {
      updateMessageMutation(
        {
          message: {
            ...chat,
            files: convertFiles(chat.files),
            sender_name: chat.sender_name ?? "AI",
            text: message,
            sender: chat.sender,
            flow_id: chat.flow_id,
            session_id: chat.session_id ?? "",
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
            text: chat.text.toString(),
            sender: chat.sender,
            flow_id: chat.flow_id,
            session_id: chat.session_id ?? "",
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

    return (
      <div className="w-full py-2">
        <div className={cn("group relative rounded-md", editMessage ? "" : "")}>
          {/* Show sender name only for AI messages */}
          <div
            className={cn("pb-1 text-xs font-medium text-muted-foreground")}
            data-testid={"sender_name_" + chat.sender_name?.toLocaleLowerCase()}
          >
            {chat.sender_name}
          </div>
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

          <div className="flex w-full gap-3 items-center">
            {/* Simplified message content */}
            <div className="w-full">
              {editMessage ? (
                <EditMessageField
                  key={`edit-message-${chat.id}`}
                  message={chat.text}
                  onEdit={(message) => {
                    handleEditMessage(message);
                  }}
                  onCancel={() => setEditMessage(false)}
                />
              ) : chat.text === "" && isBuilding && lastMessage ? (
                <IconComponent
                  name="MoreHorizontal"
                  className="h-4 w-4 animate-pulse"
                />
              ) : (
                <div
                  className={cn(
                    "whitespace-pre-wrap break-words text-sm",
                    isEmpty ? "text-muted-foreground" : "text-foreground",
                  )}
                  data-testid={`chat-message-${chat.sender_name}-${chat.text}`}
                >
                  <CustomMarkdownField
                    isAudioMessage={isAudioMessage}
                    chat={chat}
                    isEmpty={isEmpty}
                    chatMessage={chat.text}
                    editedFlag={editedFlag}
                  />
                </div>
              )}
            </div>
          </div>
          {!editMessage && (
            <div
              className={cn(
                "invisible absolute group-hover:visible -right-4 top-0",
              )}
            >
              <EditMessageButton
                onCopy={() => {
                  navigator.clipboard.writeText(chat.text);
                }}
                onDelete={() => {}}
                onEdit={() => setEditMessage(true)}
                className="h-fit group-hover:visible"
                onEvaluate={handleEvaluateAnswer}
                evaluation={chat.properties?.positive_feedback}
                isAudioMessage={isAudioMessage}
              />
            </div>
          )}
        </div>
      </div>
    );
  },
);
