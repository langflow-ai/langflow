import React from "react";
import ReactMarkdown from "react-markdown";
import { cn } from "../../../utils/utils";

interface Message {
  role: string;
  content: string;
}

interface AIMessageProps {
  message: Message;
}

export const AIMessage: React.FC<AIMessageProps> = ({ message }) => {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex flex-col",
        isUser ? "items-end" : "items-start"
      )}
    >
      <div
        className={cn(
          "max-w-[80%] rounded-lg p-3",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted"
        )}
      >
        <ReactMarkdown
          components={{
            p: ({ node, ...props }) => (
              <p className="mb-2 last:mb-0" {...props} />
            ),
            code: ({ node, className, children, ...props }) => (
              <code
                className={cn(
                  "rounded bg-black/10 px-1.5 py-0.5 font-mono text-sm",
                  className
                )}
                {...props}
              >
                {children}
              </code>
            ),
            pre: ({ node, ...props }) => (
              <pre
                className="mb-2 overflow-auto rounded bg-black/10 p-2 font-mono text-sm"
                {...props}
              />
            ),
          }}
        >
          {message.content}
        </ReactMarkdown>
      </div>
    </div>
  );
};
