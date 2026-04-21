import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax/browser";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { extractLanguage, isCodeBlock } from "@/utils/codeBlockUtils";
import { preprocessChatMessage } from "@/utils/markdownUtils";
import { markdownSanitizeSchema } from "@/utils/sanitizeSchema";
import { cn } from "@/utils/utils";
import CodeTabsComponent from "../../../../../../components/core/codeTabsComponent";

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
      const hasContent = textContent.length > 0;
      setShowWarning(!hasContent);
    } else {
      setShowWarning(false);
    }
  }, [processedChatMessage, isEmpty]);

  return (
    <div className="w-full items-baseline gap-2">
      {showWarning ? (
        <div className="text-muted-foreground text-sm p-2 border border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20 rounded">
          ⚠️ The response was filtered by security sanitization and cannot be
          displayed.
        </div>
      ) : (
        <>
          <div ref={markdownRef}>
            <Markdown
              remarkPlugins={[remarkGfm as any]}
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
                  return (
                    <h3 className={cn("mt-4", props.className)} {...props} />
                  );
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
                code: ({ node, className, children, ...props }) => {
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
                        return (
                          <span className="form-modal-markdown-span"></span>
                        );
                      }

                      // Specifically handle <think> tags that were wrapped in backticks
                      if (content === "<think>" || content === "</think>") {
                        return <span>{content}</span>;
                      }
                    }

                    if (isCodeBlock(className, props, content)) {
                      return (
                        <CodeTabsComponent
                          language={extractLanguage(className)}
                          code={String(content).replace(/\n$/, "")}
                        />
                      );
                    }

                    return (
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
          </div>
          {editedFlag}
        </>
      )}
    </div>
  );
};
