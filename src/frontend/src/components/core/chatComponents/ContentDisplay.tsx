import ForwardedIconComponent from "@/components/common/genericIconComponent";
import DurationDisplay from "@/components/core/chatComponents/DurationDisplay";
import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import { ReactNode } from "react";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax";
import remarkGfm from "remark-gfm";
import {
  CodeContent,
  ContentType,
  ErrorContent,
  JSONContent,
  MediaContent,
  TextContent,
  ToolContent,
} from "types/chat";

export default function ContentDisplay({
  content,
  chatId,
  playgroundPage,
}: {
  content: ContentType;
  chatId: string;
  playgroundPage?: boolean;
}) {
  // First render the common BaseContent elements if they exist
  const renderHeader = content.header && (
    <>
      <div className="flex items-center gap-2 pb-[12px]">
        {content.header.icon && (
          <ForwardedIconComponent
            name={content.header.icon}
            className="h-4 w-4"
            strokeWidth={1.5}
          />
        )}
        {content.header.title && (
          <>
            <Markdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeMathjax]}
              className="inline-block w-fit max-w-full text-sm font-semibold text-foreground"
            >
              {content.header.title}
            </Markdown>
          </>
        )}
      </div>
    </>
  );
  const renderDuration = content.duration !== undefined && !playgroundPage && (
    <div className="absolute right-2 top-4">
      <DurationDisplay duration={content.duration} chatId={chatId} />
    </div>
  );

  // Then render the specific content based on type
  let contentData: ReactNode | null = null;
  switch (content.type) {
    case "text":
      contentData = (
        <div className="ml-1 pr-20">
          <Markdown
            remarkPlugins={[remarkGfm]}
            linkTarget="_blank"
            rehypePlugins={[rehypeMathjax]}
            className="markdown prose max-w-full text-sm font-normal dark:prose-invert"
            components={{
              p({ node, ...props }) {
                return (
                  <span className="block w-fit max-w-full">
                    {props.children}
                  </span>
                );
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
                    <SimplifiedCodeTabComponent
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
            {String((content as TextContent).text)}
          </Markdown>
        </div>
      );
      break;

    case "code":
      contentData = (
        <div className="pr-20">
          <SimplifiedCodeTabComponent
            language={(content as CodeContent).language}
            code={(content as CodeContent).code}
          />
        </div>
      );
      break;

    case "json":
      contentData = (
        <div className="pr-20">
          <SimplifiedCodeTabComponent
            language="json"
            code={JSON.stringify((content as JSONContent).data, null, 2)}
          />
        </div>
      );
      break;

    case "error":
      contentData = (
        <div className="text-red-500">
          {(content as ErrorContent).reason && (
            <div>Reason: {(content as ErrorContent).reason}</div>
          )}
          {(content as ErrorContent).solution && (
            <div>Solution: {(content as ErrorContent).solution}</div>
          )}
          {(content as ErrorContent).traceback && (
            <SimplifiedCodeTabComponent
              language="text"
              code={(content as ErrorContent).traceback || ""}
            />
          )}
        </div>
      );
      break;

    case "tool_use":
      const formatToolOutput = (output: any) => {
        if (output === null || output === undefined) return "";

        // If it's a string, render as markdown
        if (typeof output === "string") {
          return (
            <Markdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeMathjax]}
              className="markdown prose max-w-full text-sm font-normal dark:prose-invert"
              components={{
                pre({ node, ...props }) {
                  return <>{props.children}</>;
                },
                ol({ node, ...props }) {
                  return <ol className="max-w-full">{props.children}</ol>;
                },
                ul({ node, ...props }) {
                  return <ul className="max-w-full">{props.children}</ul>;
                },
                code: ({ node, inline, className, children, ...props }) => {
                  const match = /language-(\w+)/.exec(className || "");
                  return !inline ? (
                    <SimplifiedCodeTabComponent
                      language={(match && match[1]) || ""}
                      code={String(children).replace(/\n$/, "")}
                    />
                  ) : (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {output}
            </Markdown>
          );
        }

        // For objects/arrays, format as JSON
        return (
          <SimplifiedCodeTabComponent
            language="json"
            code={JSON.stringify(output, null, 2)}
          />
        );
      };

      contentData = (
        <div>
          {(content as ToolContent).tool_code && (
            <SimplifiedCodeTabComponent
              language="python"
              code={(content as ToolContent).tool_code}
            />
          )}
          {(content as ToolContent).tool_output && (
            <div className="mt-2">
              {formatToolOutput((content as ToolContent).tool_output)}
            </div>
          )}
        </div>
      );
      break;

    case "media":
      contentData = (
        <div className="flex w-full justify-center">
          <img
            className="max-h-[300px] max-w-full rounded-md object-contain"
            src={(content as MediaContent).media_url}
            alt={(content as MediaContent).media_alt}
          />
        </div>
      );
      break;

    case "link":
      contentData = (
        <div className="flex w-full justify-center">
          <a
            href={(content as MediaContent).media_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-500 underline"
          >
            {(content as MediaContent).media_url}
          </a>
        </div>
      );
      break;

    default:
      contentData = null;
  }

  return (
    <div>
      {renderHeader}
      {renderDuration}
      {contentData}
    </div>
  );
}
