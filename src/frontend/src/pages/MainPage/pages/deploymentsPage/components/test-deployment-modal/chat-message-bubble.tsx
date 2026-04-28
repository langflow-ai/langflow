import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import { cn } from "@/utils/utils";
import type { ChatMessage } from "./types";

function formatTraceValue(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function ToolTraceItem({
  trace,
}: {
  trace: NonNullable<ChatMessage["toolTraces"]>[number];
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded border border-border overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-muted/50 transition-colors"
      >
        <ForwardedIconComponent
          name={open ? "ChevronDown" : "ChevronRight"}
          className="h-3 w-3 flex-shrink-0 text-muted-foreground"
        />
        <ForwardedIconComponent
          name="Wrench"
          className="h-3 w-3 flex-shrink-0 text-muted-foreground"
        />
        <span className="font-medium text-foreground truncate">
          {trace.toolName}
        </span>
        {trace.agentName && (
          <span className="ml-auto text-muted-foreground truncate text-[10px]">
            {trace.agentName}
          </span>
        )}
      </button>
      {open && (
        <div className="border-t border-border px-2 py-1.5 flex flex-col gap-1.5">
          {trace.input !== undefined && (
            <div>
              <div className="text-muted-foreground mb-0.5 font-medium">
                Input
              </div>
              <pre className="overflow-x-auto rounded bg-muted p-1.5 text-xs whitespace-pre-wrap break-all">
                {formatTraceValue(trace.input)}
              </pre>
            </div>
          )}
          {trace.output !== undefined && (
            <div>
              <div className="text-muted-foreground mb-0.5 font-medium">
                Output
              </div>
              <pre className="overflow-x-auto rounded bg-muted p-1.5 text-xs whitespace-pre-wrap break-all">
                {formatTraceValue(trace.output)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ToolTracesPanel({
  traces,
}: {
  traces: NonNullable<ChatMessage["toolTraces"]>;
}) {
  return (
    <div className="mt-2 flex flex-col gap-1 text-xs">
      {traces.map((trace, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: traces have no stable id
        <ToolTraceItem key={i} trace={trace} />
      ))}
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
              components={{
                code({ className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className ?? "");
                  const isBlock = !props.ref;
                  if (isBlock && match) {
                    return (
                      <SimplifiedCodeTabComponent
                        code={String(children).replace(/\n$/, "")}
                        language={match[1]}
                      />
                    );
                  }
                  return (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
              }}
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
