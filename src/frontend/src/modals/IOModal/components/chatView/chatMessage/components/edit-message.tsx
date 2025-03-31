import { cn } from "@/utils/utils";

import { EMPTY_OUTPUT_SEND_MESSAGE } from "@/constants/constants";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax";
import remarkGfm from "remark-gfm";
import CodeTabsComponent from "../../../../../../components/core/codeTabsComponent/ChatCodeTabComponent";

type MarkdownFieldProps = {
  chat: any;
  isEmpty: boolean;
  chatMessage: string;
  editedFlag: React.ReactNode;
};

export const MarkdownField = ({
  chat,
  isEmpty,
  chatMessage,
  editedFlag,
}: MarkdownFieldProps) => {
  return (
    <div className="w-full items-baseline gap-2">
      <Markdown
        remarkPlugins={[remarkGfm]}
        linkTarget="_blank"
        rehypePlugins={[rehypeMathjax]}
        className={cn(
          "markdown prose flex w-fit max-w-full flex-col items-baseline text-[14px] font-normal word-break-break-word dark:prose-invert",
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
        {isEmpty && !chat.stream_url ? EMPTY_OUTPUT_SEND_MESSAGE : chatMessage}
      </Markdown>
      {editedFlag}
    </div>
  );
};
