import { MarkdownField } from "@/modals/IOModal/components/chatView/chatMessage/components/edit-message";

type CustomMarkdownFieldProps = {
  isAudioMessage: boolean;
  chat: any;
  isEmpty: boolean;
  chatMessage: string;
  editedFlag: React.ReactNode;
  onChatInteraction?: (action: string, data?: any) => void;
};
export const CustomMarkdownField = ({
  isAudioMessage,
  chat,
  isEmpty,
  chatMessage,
  editedFlag,
  onChatInteraction,
}: CustomMarkdownFieldProps) => {
  return (
    <>
      <MarkdownField
        isAudioMessage={isAudioMessage}
        chat={chat}
        isEmpty={isEmpty}
        chatMessage={chatMessage}
        editedFlag={editedFlag}
        onChatInteraction={onChatInteraction}
      />
    </>
  );
};
