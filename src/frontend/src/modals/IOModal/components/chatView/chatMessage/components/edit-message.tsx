import { EMPTY_OUTPUT_SEND_MESSAGE } from "@/constants/constants";
import { cn } from "@/utils/utils";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";
import CodeTabsComponent from "../../../../../../components/core/codeTabsComponent";

type MarkdownFieldProps = {
  chat: any;
  isEmpty: boolean;
  chatMessage: string;
  editedFlag: React.ReactNode;
  isAudioMessage?: boolean;
};

// Function to replace <think> tags with a placeholder before markdown processing
const preprocessChatMessage = (text: string): string => {
  // Replace <think> tags with `<span class="think-tag">think:</span>`
  return text
    .replace(/<think>/g, "`<think>`")
    .replace(/<\/think>/g, "`</think>`");
};

export const MarkdownField = ({
  chat,
  isEmpty,
  chatMessage,
  editedFlag,
  isAudioMessage,
}: MarkdownFieldProps) => {
  // Process the chat message to handle <think> tags
  const processedChatMessage = preprocessChatMessage(chatMessage);

  return (
    <div className="w-full items-baseline gap-2">
      <Markdown
        remarkPlugins={[remarkGfm as any]}
        linkTarget="_blank"
        rehypePlugins={[rehypeMathjax, rehypeRaw]}
        className={cn(
          "markdown prose flex w-fit max-w-full flex-col items-baseline text-sm font-normal word-break-break-word dark:prose-invert",
          isEmpty ? "text-muted-foreground" : "text-primary",
        )}
        components={{
          p({ node, ...props }) {
            return <span className="w-fit max-w-full">{props.children}</span>;
          },
          ol({ node, ...props }) {
            return <ol className="max-w-full">{props.children}</ol>;
          },
          ul({ node, ...props }) {
            return <ul className="max-w-full">{props.children}</ul>;
          },
          pre({ node, ...props }) {
            return <>{props.children}</>;
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
          ? EMPTY_OUTPUT_SEND_MESSAGE
          : processedChatMessage}
      </Markdown>
      {editedFlag}
    </div>
  );
};
