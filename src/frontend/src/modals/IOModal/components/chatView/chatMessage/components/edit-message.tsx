import { useTranslation } from "react-i18next";
import { SanitizedMarkdown } from "@/components/core/sanitizedMarkdown";

type MarkdownFieldProps = {
  chat: any;
  isEmpty: boolean;
  chatMessage: string;
  editedFlag: React.ReactNode;
  isAudioMessage?: boolean;
};

export const MarkdownField = ({
  chat,
  isEmpty,
  chatMessage,
  editedFlag,
  isAudioMessage,
}: MarkdownFieldProps) => {
  const { t } = useTranslation();

  return (
    <div className="w-full items-baseline gap-2">
      <SanitizedMarkdown
        chatMessage={chatMessage}
        isEmpty={isEmpty}
        emptyMessage={
          isEmpty && !chat.stream_url
            ? t("chat.emptyOutputSendMessage")
            : undefined
        }
      />
      {editedFlag}
    </div>
  );
};
