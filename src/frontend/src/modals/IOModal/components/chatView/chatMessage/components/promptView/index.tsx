import { EMPTY_INPUT_SEND_MESSAGE } from "@/constants/constants";
import { ChatMessageType } from "@/types/chat";
import { cn } from "@/utils/utils";
import { Dispatch, SetStateAction } from "react";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../../../../components/common/genericIconComponent";

type PromptViewProps = {
  promptOpen: boolean;
  setPromptOpen: Dispatch<SetStateAction<boolean>>;
  template: string;
  chat: ChatMessageType;
  isEmpty: boolean;
  chatMessage: string;
};

export const PromptView = ({
  promptOpen,
  setPromptOpen,
  template,
  chat,
  isEmpty,
  chatMessage,
}: PromptViewProps) => {
  return (
    <>
      <button
        className="form-modal-initial-prompt-btn"
        onClick={() => {
          setPromptOpen((old) => !old);
        }}
      >
        Display Prompt
        <IconComponent
          name="ChevronDown"
          className={`h-3 w-3 transition-all ${promptOpen ? "rotate-180" : ""}`}
        />
      </button>
      <span
        className={cn(
          "prose text-[14px] font-normal word-break-break-word dark:prose-invert",
          !isEmpty ? "text-primary" : "text-muted-foreground",
        )}
      >
        {promptOpen
          ? template?.split("\n")?.map((line, index) => {
              const regex = /{([^}]+)}/g;
              let match;
              let parts: Array<JSX.Element | string> = [];
              let lastIndex = 0;
              while ((match = regex.exec(line)) !== null) {
                // Push text up to the match
                if (match.index !== lastIndex) {
                  parts.push(line.substring(lastIndex, match.index));
                }
                // Push div with matched text
                if (chat.message[match[1]]) {
                  parts.push(
                    <span className="chat-message-highlight">
                      {chat.message[match[1]]}
                    </span>,
                  );
                }

                // Update last index
                lastIndex = regex.lastIndex;
              }
              // Push text after the last match
              if (lastIndex !== line.length) {
                parts.push(line.substring(lastIndex));
              }
              return <p>{parts}</p>;
            })
          : isEmpty
            ? EMPTY_INPUT_SEND_MESSAGE
            : chatMessage}
      </span>
    </>
  );
};
