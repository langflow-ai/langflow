import { AlertCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax/browser";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import CodeTabsComponent from "@/components/core/codeTabsComponent";
import { preprocessChatMessage } from "@/utils/markdownUtils";
import { cn } from "@/utils/utils";

type MarkdownFieldProps = {
  chat: {
    stream_url?: string | null;
    properties?: Record<string, unknown>;
  };
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
  const [showSanitizationWarning, setShowSanitizationWarning] = useState(false);

  // Memoize preprocessing to avoid repeated work on re-renders
  const processedChatMessage = useMemo(() => {
    // Short-circuit for empty messages
    if (!chatMessage || chatMessage.trim() === "") {
      return "";
    }

    // Process the chat message to handle <think> tags and clean up tables
    return preprocessChatMessage(chatMessage);
  }, [chatMessage]);

  // Detect if content might have been sanitized (contains HTML tags but no code blocks)
  useEffect(() => {
    if (!chatMessage) {
      setShowSanitizationWarning(false);
      return;
    }

    // Check if message contains HTML-like tags
    const hasHtmlTags = /<[a-z][\s\S]*>/i.test(chatMessage);
    // Check if it's in a code block
    const hasCodeBlock = /```[\s\S]*```|`[^`]+`/.test(chatMessage);

    // Show warning if there are HTML tags but they're not in code blocks
    setShowSanitizationWarning(hasHtmlTags && !hasCodeBlock);
  }, [chatMessage]);

  return (
    <div className="w-full items-baseline gap-2">
      {showSanitizationWarning && (
        <div className="mb-3 flex items-start gap-2 rounded-md border border-yellow-500/50 bg-yellow-500/10 p-3 text-sm text-yellow-700 dark:text-yellow-400">
          <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
          <div>
            <strong>HTML content was sanitized for security.</strong>
            <br />
            To display HTML code, please wrap it in code blocks using triple
            backticks (```html).
          </div>
        </div>
      )}
      <Markdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeMathjax, rehypeRaw, rehypeSanitize]}
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
            return <hr className="w-full mt-3 mb-5 border-border" {...props} />;
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
          code: ({ node, inline, className, children, ...props }) => {
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
        {isEmpty && !chat.stream_url
          ? t("chat.emptyOutputSendMessage")
          : processedChatMessage}
      </Markdown>
      {editedFlag}
    </div>
  );
};
