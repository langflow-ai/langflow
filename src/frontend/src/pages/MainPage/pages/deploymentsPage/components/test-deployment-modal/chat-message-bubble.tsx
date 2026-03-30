import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import type { ChatMessage } from "./types";

function ToolTracesPanel({
  traces,
}: {
  traces: NonNullable<ChatMessage["toolTraces"]>;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-2 text-xs">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-muted-foreground hover:text-foreground"
      >
        <span>{open ? "▾" : "▸"}</span>
        <span>Tool details ({traces.length})</span>
      </button>
      {open && (
        <div className="mt-1 flex flex-col gap-2">
          {traces.map((trace, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: traces have no stable id
            <div key={i} className="rounded border border-border p-2">
              <div className="font-medium text-foreground mb-1">
                {trace.toolName}
              </div>
              {trace.input !== undefined && (
                <div className="mb-1">
                  <div className="text-muted-foreground mb-0.5">Input</div>
                  <pre className="overflow-x-auto rounded bg-muted p-1 text-xs">
                    {JSON.stringify(trace.input, null, 2)}
                  </pre>
                </div>
              )}
              {trace.output !== undefined && (
                <div>
                  <div className="text-muted-foreground mb-0.5">Output</div>
                  <pre className="overflow-x-auto rounded bg-muted p-1 text-xs">
                    {JSON.stringify(trace.output, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function LoadingDots() {
  return (
    <div className="flex items-center gap-1 py-1">
      <div className="size-1 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.3s]" />
      <div className="size-1 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.15s]" />
      <div className="size-1 rounded-full bg-muted-foreground animate-bounce" />
    </div>
  );
}

function Avatar({
  isUser,
  className,
}: {
  isUser: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full",
        isUser
          ? "bg-primary text-primary-foreground"
          : "border border-border bg-muted",
        className,
      )}
    >
      <ForwardedIconComponent
        name={isUser ? "User" : "Bot"}
        className="h-4 w-4"
      />
    </div>
  );
}

interface ChatMessageBubbleProps {
  message: ChatMessage;
}

export default function ChatMessageBubble({ message }: ChatMessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex w-full items-center gap-2",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
    >
      <Avatar isUser={isUser} />
      <div
        className={cn(
          "max-w-[75%] rounded-lg px-3 py-2 text-sm bg-muted text-foreground",
        )}
      >
        {message.isLoading ? (
          <LoadingDots />
        ) : message.error ? (
          <span className="text-destructive">{message.error}</span>
        ) : isUser ? (
          <span className="whitespace-pre-wrap">{message.content}</span>
        ) : (
          <>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              className="prose prose-sm dark:prose-invert max-w-none"
            >
              {message.content}
            </ReactMarkdown>
            {message.toolTraces && message.toolTraces.length > 0 && (
              <ToolTracesPanel traces={message.toolTraces} />
            )}
          </>
        )}
      </div>
    </div>
  );
}
