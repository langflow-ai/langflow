import ForwardedIconComponent from "components/common/genericIconComponent";
import DurationDisplay from "components/core/chatComponents/DurationDisplay";
import SimplifiedCodeTabComponent from "components/core/codeTabsComponent/ChatCodeTabComponent";
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

const ICON_SIZE = 16;

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
              className="inline-block w-fit max-w-full text-[14px] font-semibold text-foreground"
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
            className="markdown prose max-w-full text-[14px] font-normal dark:prose-invert"
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
              className="markdown prose max-w-full text-[14px] font-normal dark:prose-invert"
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
        try {
          return (
            <SimplifiedCodeTabComponent
              language="json"
              code={JSON.stringify(output, null, 2)}
            />
          );
        } catch {
          return String(output);
        }
      };

      contentData = (
        <div className="flex flex-col gap-2">
          <Markdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeMathjax]}
            className="markdown prose max-w-full text-[14px] font-normal dark:prose-invert"
          >
            **Input:**
          </Markdown>
          <SimplifiedCodeTabComponent
            language="json"
            code={JSON.stringify((content as ToolContent).tool_input, null, 2)}
          />
          {(content as ToolContent).output && (
            <>
              <Markdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeMathjax]}
                className="markdown max_w-full prose text-[14px] font-normal dark:prose-invert"
              >
                **Output:**
              </Markdown>
              <div className="mt-1">
                {formatToolOutput((content as ToolContent).output)}
              </div>
            </>
          )}
          {(content as ToolContent).error && (
            <div className="text-red-500">
              <Markdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeMathjax]}
                className="markdown max_w-full prose text-[14px] font-normal dark:prose-invert"
              >
                **Error:**
              </Markdown>
              <SimplifiedCodeTabComponent
                language="json"
                code={JSON.stringify((content as ToolContent).error, null, 2)}
              />
            </div>
          )}
        </div>
      );
      break;

    case "media":
      contentData = (
        <div>
          {(content as MediaContent).urls.map((url, index) => (
            <img
              key={index}
              src={url}
              alt={(content as MediaContent).caption || `Media ${index}`}
            />
          ))}
          {(content as MediaContent).caption && (
            <div>{(content as MediaContent).caption}</div>
          )}
        </div>
      );
      break;
  }

  return (
    <div className="relative p-[16px]">
      {renderHeader}
      {renderDuration}
      {contentData}
    </div>
  );
}
