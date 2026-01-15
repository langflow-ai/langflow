import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import type { AssistantMessage } from "../assistant.types";
import { ComponentResultLine } from "./component-result-line";

type MessageLineProps = {
  message: AssistantMessage;
  onAddToCanvas: (code: string) => Promise<void>;
  onSaveToSidebar: (code: string, className: string) => Promise<void>;
};

const getMessageStyle = (type: AssistantMessage["type"]): string => {
  switch (type) {
    case "input":
      return "text-accent-emerald-foreground";
    case "output":
      return "text-foreground";
    case "error":
      return "text-destructive";
    case "system":
      return "text-muted-foreground italic";
    case "validated":
      return "text-accent-emerald-foreground";
    case "validation_error":
      return "text-accent-amber-foreground";
    default:
      return "text-foreground";
  }
};

const getPrefix = (type: AssistantMessage["type"]): string => {
  switch (type) {
    case "input":
      return "> ";
    case "error":
      return "! ";
    case "system":
      return "# ";
    default:
      return "";
  }
};

export const MessageLine = ({
  message,
  onAddToCanvas,
  onSaveToSidebar,
}: MessageLineProps) => {
  if (
    message.type === "validated" &&
    message.metadata?.componentCode &&
    message.metadata?.className
  ) {
    return (
      <ComponentResultLine
        className={message.metadata.className}
        code={message.metadata.componentCode}
        onAddToCanvas={onAddToCanvas}
        onSaveToSidebar={onSaveToSidebar}
      />
    );
  }

  const useMarkdown = message.type === "output";

  return (
    <div className="flex flex-col gap-1">
      {message.type === "validation_error" && (
        <div className="flex items-center gap-1.5 py-1">
          <ForwardedIconComponent
            name="XCircle"
            className="h-4 w-4 text-destructive"
          />
          <span className="text-sm text-destructive">Validation failed</span>
        </div>
      )}
      {useMarkdown ? (
        <div className="whitespace-pre-wrap font-mono text-sm text-foreground">
          <span className="select-none text-muted-foreground">← </span>
          {message.content}
        </div>
      ) : (
        <div
          className={cn(
            "whitespace-pre-wrap font-mono text-sm",
            getMessageStyle(message.type),
          )}
        >
          <span className="select-none opacity-70">{getPrefix(message.type)}</span>
          {message.content}
        </div>
      )}
    </div>
  );
};
