import { cn } from "@/utils/utils";
import type { AssistantMessage } from "../assistant.types";

type SystemMessageProps = {
  content: string;
  type: AssistantMessage["type"];
};

const getMessageStyle = (type: AssistantMessage["type"]): string => {
  switch (type) {
    case "error":
      return "text-destructive";
    case "system":
      return "text-muted-foreground italic";
    default:
      return "text-foreground";
  }
};

const getPrefix = (type: AssistantMessage["type"]): string => {
  switch (type) {
    case "error":
      return "! ";
    case "system":
      return "# ";
    default:
      return "";
  }
};

export const SystemMessage = ({ content, type }: SystemMessageProps) => {
  return (
    <div
      className={cn(
        "whitespace-pre-wrap font-mono text-sm",
        getMessageStyle(type),
      )}
    >
      <span className="select-none opacity-70">{getPrefix(type)}</span>
      {content}
    </div>
  );
};
