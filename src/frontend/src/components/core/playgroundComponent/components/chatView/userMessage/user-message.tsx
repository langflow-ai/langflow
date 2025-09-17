import { memo, useState } from "react";
import { useUpdateMessage } from "@/controllers/API/queries/messages";
import { CustomProfileIcon } from "@/customization/components/custom-profile-icon";
import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import useFlowStore from "@/stores/flowStore";
import { EMPTY_INPUT_SEND_MESSAGE } from "../../../../../../constants/constants";
import useAlertStore from "../../../../../../stores/alertStore";
import type { chatMessagePropsType } from "../../../../../../types/components";
import { cn } from "../../../../../../utils/utils";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../../common/genericIconComponent";
import EditMessageField from "./components/edit-message-field";
import FileCardWrapper from "./components/file-card-wrapper";
import { EditMessageButton } from "./components/message-options";
import { convertFiles } from "./helpers/convert-files";

export const UserMessage = memo(
  ({ chat, lastMessage, playgroundPage }: chatMessagePropsType) => {
    const setErrorData = useAlertStore((state) => state.setErrorData);
    const [editMessage, setEditMessage] = useState(false);
    const isBuilding = useFlowStore((state) => state.isBuilding);

    const isAudioMessage = chat.category === "audio";

    const isEmpty = chat.text?.trim() === "";
    const { mutate: updateMessageMutation } = useUpdateMessage({
      flowId: chat.flow_id,
      sessionId: chat.session_id ?? "",
    });

    const handleEditMessage = (message: string) => {
      updateMessageMutation(
        {
          ...chat,
          files: convertFiles(chat.files),
          sender_name: chat.sender_name ?? "AI",
          text: message,
          sender: chat.sender,
          flow_id: chat.flow_id,
          session_id: chat.session_id ?? "",
        },
        {
          onSuccess: () => {
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

    return (
      <div className="w-full py-2 flex justify-end">
        <div
          className={cn(
            "group relative rounded-xl bg-muted border border-border px-3 py-2 w-full",
            editMessage ? "" : "",
          )}
        >
          <div className="flex w-full gap-3 items-center">
            <div className=" h-[24px] w-[24px] items-center justify-center inline-flex">
              {chat.properties?.icon ? (
                chat.properties.icon.match(
                  /[\u2600-\u27BF\uD83C-\uDBFF\uDC00-\uDFFF]/,
                ) ? (
                  <div className="">{chat.properties.icon}</div>
                ) : (
                  <ForwardedIconComponent name={chat.properties.icon} />
                )
              ) : !ENABLE_DATASTAX_LANGFLOW && !playgroundPage ? (
                <CustomProfileIcon />
              ) : playgroundPage ? (
                <ForwardedIconComponent name="User" />
              ) : (
                <CustomProfileIcon />
              )}
            </div>

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
              ) : (
                <>
                  {chat.text === "" && isBuilding && lastMessage ? (
                    <IconComponent
                      name="MoreHorizontal"
                      className="h-4 w-4 animate-pulse"
                    />
                  ) : (
                    <div
                      className={cn(
                        "whitespace-pre-wrap break-words text-sm text-foreground",
                      )}
                      data-testid={`chat-message-${chat.sender_name}-${chat.text}`}
                    >
                      {isEmpty ? EMPTY_INPUT_SEND_MESSAGE : chat.text}
                    </div>
                  )}

                  {/* File attachments */}
                  {chat.files && (
                    <div className="mt-2 flex flex-col gap-2">
                      {chat.files?.map((file) => {
                        return <FileCardWrapper path={file} key={file} />;
                      })}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
          {!editMessage && (
            <div className="invisible absolute group-hover:visible -left-4 top-0">
              <EditMessageButton
                onCopy={() => {
                  navigator.clipboard.writeText(chat.text);
                }}
                onEdit={() => setEditMessage(true)}
                className="h-fit group-hover:visible"
                isAudioMessage={isAudioMessage}
              />
            </div>
          )}
        </div>
      </div>
    );
  },
);
