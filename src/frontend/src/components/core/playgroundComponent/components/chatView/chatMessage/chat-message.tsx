import { useEffect, useRef, useState } from "react";
import { ContentBlockDisplay } from "@/components/core/chatComponents/ContentBlockDisplay";
import { useUpdateMessage } from "@/controllers/API/queries/messages";
import { CustomMarkdownField } from "@/customization/components/custom-markdown-field";
import { CustomProfileIcon } from "@/customization/components/custom-profile-icon";
import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { EMPTY_INPUT_SEND_MESSAGE } from "../../../../../../constants/constants";
import useAlertStore from "../../../../../../stores/alertStore";
import type { chatMessagePropsType } from "../../../../../../types/components";
import { cn } from "../../../../../../utils/utils";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../../common/genericIconComponent";
import { ErrorView } from "./components/content-view";
import EditMessageField from "./components/edit-message-field";
import FileCardWrapper from "./components/file-card-wrapper";
import { EditMessageButton } from "./components/message-options";
import { convertFiles } from "./helpers/convert-files";

export default function ChatMessage({
  chat,
  lastMessage,
  updateChat,
  playgroundPage,
}: chatMessagePropsType): JSX.Element {
  const flow_id = useFlowsManagerStore((state) => state.currentFlowId);
  const fitViewNode = useFlowStore((state) => state.fitViewNode);
  // We need to check if message is not undefined because
  // we need to run .toString() on it
  const [chatMessage, setChatMessage] = useState(
    chat.text ? chat.text.toString() : "",
  );
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const chatMessageRef = useRef(chatMessage);
  const [editMessage, setEditMessage] = useState(false);
  const [showError, setShowError] = useState(false);
  const isBuilding = useFlowStore((state) => state.isBuilding);

  const isAudioMessage = chat.category === "audio";

  useEffect(() => {
    const chatMessageString = chat.text ? chat.text.toString() : "";
    setChatMessage(chatMessageString);
    chatMessageRef.current = chatMessage;
  }, [chat, isBuilding]);

  useEffect(() => {
    if (chat.category === "error") {
      // Short delay before showing error to allow for loading animation
      const timer = setTimeout(() => {
        setShowError(true);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [chat.category]);

  let decodedMessage = chatMessage ?? "";
  try {
    decodedMessage = decodeURIComponent(chatMessage);
  } catch (_e) {
    // console.error(e);
  }
  const isEmpty = decodedMessage?.trim() === "";
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
          flow_id,
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
          flow_id,
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

  if (chat.category === "error") {
    const blocks = chat.content_blocks ?? [];

    return (
      <ErrorView
        blocks={blocks}
        showError={showError}
        lastMessage={lastMessage}
        fitViewNode={fitViewNode}
        chat={chat}
      />
    );
  }
  const isSend = chat.sender === "User";

  return (
    <>
      <div className={cn("w-full py-2", isSend ? "flex justify-end" : "")}>
        <div
          className={cn(
            "group relative",
            isSend
              ? "rounded-xl bg-muted border border-border px-3 py-2 w-full"
              : "rounded-md",
            editMessage ? "" : "",
          )}
        >
          {/* Show sender name only for AI messages */}
          {!isSend && (
            <div
              className={cn("pb-1 text-xs font-medium text-muted-foreground")}
              data-testid={
                "sender_name_" + chat.sender_name?.toLocaleLowerCase()
              }
            >
              {chat.sender_name}
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
            />
          )}

          <div className="flex w-full gap-3 items-center">
            {isSend && (
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
            )}

            {/* Simplified message content */}
            <div className="w-full">
              {editMessage ? (
                <EditMessageField
                  key={`edit-message-${chat.id}`}
                  message={decodedMessage}
                  onEdit={(message) => {
                    handleEditMessage(message);
                  }}
                  onCancel={() => setEditMessage(false)}
                />
              ) : (
                <>
                  {chatMessage === "" && isBuilding && lastMessage ? (
                    <IconComponent
                      name="MoreHorizontal"
                      className="h-4 w-4 animate-pulse"
                    />
                  ) : (
                    <div
                      className={cn(
                        "whitespace-pre-wrap break-words text-sm",
                        isSend
                          ? "text-foreground"
                          : isEmpty
                            ? "text-muted-foreground"
                            : "text-foreground",
                      )}
                      data-testid={`chat-message-${chat.sender_name}-${chatMessage}`}
                    >
                      {isSend ? (
                        isEmpty ? (
                          EMPTY_INPUT_SEND_MESSAGE
                        ) : (
                          decodedMessage
                        )
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

                  {/* File attachments */}
                  {chat.files && (
                    <div className="mt-2 flex flex-col gap-2">
                      {chat.files?.map((file, index) => {
                        return (
                          <FileCardWrapper
                            index={index}
                            path={file}
                            key={index}
                          />
                        );
                      })}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
          {!editMessage && (
            <div
              className={cn(
                "invisible absolute group-hover:visible",
                isSend ? "-left-4 top-0" : "-right-4 top-0",
              )}
            >
              <EditMessageButton
                onCopy={() => {
                  navigator.clipboard.writeText(chatMessage);
                }}
                onDelete={() => {}}
                onEdit={() => setEditMessage(true)}
                className="h-fit group-hover:visible"
                isBotMessage={!isSend}
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
}
