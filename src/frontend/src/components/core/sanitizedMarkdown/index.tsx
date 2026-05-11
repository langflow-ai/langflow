import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax/browser";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import CodeTabsComponent from "@/components/core/codeTabsComponent";
import { preprocessChatMessage } from "@/utils/markdownUtils";
import { markdownSanitizeSchema } from "@/utils/sanitizeSchema";
import { cn } from "@/utils/utils";

type SanitizedMarkdownProps = {
  chatMessage: string;
  isEmpty: boolean;
  emptyMessage?: string;
  className?: string;
};

/**
 * Shared component for rendering sanitized markdown content
 * Uses rehype-sanitize to prevent XSS attacks while allowing safe HTML/markdown
 */
export const SanitizedMarkdown = ({
  chatMessage,
  isEmpty,
  emptyMessage,
  className,
}: SanitizedMarkdownProps) => {
  const { t } = useTranslation();
  const markdownRef = useRef<HTMLDivElement>(null);
  const [showWarning, setShowWarning] = useState(false);

  // Memoize preprocessing to avoid repeated work on re-renders
  const processedChatMessage = useMemo(() => {
    // Short-circuit for empty messages
    if (!chatMessage || chatMessage.trim() === "") {
      return "";
    }

    // Process the chat message to handle <think> tags and clean up tables
    return preprocessChatMessage(chatMessage);
  }, [chatMessage]);

  // Check if rendered content is empty after sanitization
  useEffect(() => {
    if (markdownRef.current && processedChatMessage && !isEmpty) {
      const textContent = markdownRef.current.textContent?.trim() || "";
      // Check for media/layout elements that don't have text content
      const hasMediaElements =
        markdownRef.current.querySelector("img, hr, video, audio") !== null;
      const hasContent = textContent.length > 0 || hasMediaElements;
      setShowWarning(!hasContent);
    } else {
      setShowWarning(false);
    }
  }, [processedChatMessage, isEmpty]);

  return (
    <div ref={markdownRef} className={className}>
      {showWarning && (
        <div className="text-muted-foreground text-sm p-2 border border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20 rounded mb-2">
          ⚠️ The response was filtered by security sanitization and cannot be
          displayed.
        </div>
      )}
      {!showWarning && (
        <Markdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[
            rehypeMathjax,
            rehypeRaw,
            [rehypeSanitize, markdownSanitizeSchema],
          ]}
          className={cn(
            "markdown prose flex w-full max-w-full flex-col items-baseline text-sm font-normal word-break-break-word dark:prose-invert",
            isEmpty ? "text-muted-foreground" : "text-primary",
          )}
          components={{
            p({ node, ...props }) {
              return (
                <p className="w-fit max-w-full my-1.5 last:mb-0 first:mt-0">
                  {props.children}
                </p>
              );
            },
            ol({ node, ...props }) {
              return <ol className="max-w-full">{props.children}</ol>;
            },
            ul({ node, ...props }) {
              return <ul className="max-w-full mb-2">{props.children}</ul>;
            },
            pre({ node, ...props }) {
              return <>{props.children}</>;
            },
            hr({ node, ...props }) {
              return (
                <hr className="w-full mt-3 mb-5 border-border" {...props} />
              );
            },
            h3({ node, ...props }) {
              return <h3 className={cn("mt-4", props.className)} {...props} />;
            },
            table: ({ node, ...props }) => {
              return (
                <div className="max-w-full overflow-hidden rounded-md border bg-muted">
                  <div className="max-h-[600px] w-full overflow-auto p-4">
                    <table className="!my-0 w-full">{props.children}</table>
                  </div>
                </div>
              );
            },
            code: ({ node, inline, className, children, ...props }: any) => {
              let content = children as string;
              if (
                Array.isArray(children) &&
                children.length === 1 &&
                typeof children[0] === "string"
              ) {
                content = children[0] as string;
              }
              if (typeof content === "string") {
                if (content.length) {
                  if (content[0] === "▍") {
                    return <span className="form-modal-markdown-span"></span>;
                  }

                  // Specifically handle <think> tags that were wrapped in backticks
                  if (content === "<think>" || content === "</think>") {
                    return <span>{content}</span>;
                  }
                }

                const match = /language-(\w+)/.exec(className || "");

                return !inline ? (
                  <CodeTabsComponent
                    language={(match && match[1]) || ""}
                    code={String(content).replace(/\n$/, "")}
                  />
                ) : (
                  <code className={className} {...props}>
                    {content}
                  </code>
                );
              }
            },
          }}
        >
          {isEmpty ? emptyMessage || "" : processedChatMessage}
        </Markdown>
      )}
    </div>
  );
};
