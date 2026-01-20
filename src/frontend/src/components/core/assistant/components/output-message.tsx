import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import LangflowLogo from "@/assets/LangflowLogoColor.svg?react";

type OutputMessageProps = {
  content: string;
};

export const OutputMessage = ({ content }: OutputMessageProps) => {
  return (
    <div className="flex items-center gap-2">
      <LangflowLogo className="h-4 w-4 flex-shrink-0" />
      <Markdown
        remarkPlugins={[remarkGfm]}
        className="markdown prose prose-sm max-w-full font-mono dark:prose-invert prose-p:my-0 prose-pre:my-0 prose-ul:my-0 prose-ol:my-0 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
        components={{
          a: ({ node, ...props }) => (
            <a
              {...props}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              {props.children}
            </a>
          ),
          code: ({ node, className, children, ...props }) => {
            const isInline = !className;
            if (isInline) {
              return (
                <code
                  className="rounded bg-muted px-1 py-0.5 font-mono text-xs"
                  {...props}
                >
                  {children}
                </code>
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
        {content}
      </Markdown>
    </div>
  );
};
