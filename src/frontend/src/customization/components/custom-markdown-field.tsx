import { MarkdownField } from "@/components/core/playgroundComponent/components/chatView/botMessage/components/edit-message";

type CustomMarkdownFieldProps = {
  isAudioMessage: boolean;
  chat: any;
  isEmpty: boolean;
  chatMessage: string;
  editedFlag: React.ReactNode;
};
export const CustomMarkdownField = ({
  isAudioMessage,
  chat,
  isEmpty,
  chatMessage,
  editedFlag,
}: CustomMarkdownFieldProps) => {
  return (
    <>
      <MarkdownField
        isAudioMessage={isAudioMessage}
        chat={chat}
        isEmpty={isEmpty}
        chatMessage={chatMessage}
        editedFlag={editedFlag}
      />
    </>
  );
};
