import { CodeBlock } from "@/modals/IOModal/components/chatView/chatMessage/codeBlock";
import { ContentType } from "@/types/chat";
import { ReactNode } from "react";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax";
import remarkGfm from "remark-gfm";
import SimplifiedCodeTabComponent from "../codeTabsComponent/ChatCodeTabComponent";
import ForwardedIconComponent from "../genericIconComponent";
import DurationDisplay from "./DurationDisplay";

export default function ContentDisplay({ content }: { content: ContentType }) {
  // First render the common BaseContent elements if they exist
  const renderHeader = content.header && (
    <>
      <div className="flex items-center gap-2">
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
              className="inline-block w-fit max-w-full"
            >
              {content.header.title}
            </Markdown>
          </>
        )}
      </div>
    </>
  );
  const renderDuration = content.duration !== undefined && (
    <div className="absolute right-2 top-0">
      <DurationDisplay duration={content.duration} />
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
                  <span className="inline-block w-fit max-w-full">
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
            {String(content.text)}
          </Markdown>
        </div>
      );
      break;

    case "code":
      contentData = (
        <div className="pr-20">
          <SimplifiedCodeTabComponent
            language={content.language}
            code={content.code}
          />
        </div>
      );
      break;

    case "json":
      contentData = (
        <div className="pr-20">
          <CodeBlock
            language="json"
            value={JSON.stringify(content.data, null, 2)}
          />
        </div>
      );
      break;

    case "error":
      contentData = (
        <div className="text-red-500">
          {content.reason && <div>Reason: {content.reason}</div>}
          {content.solution && <div>Solution: {content.solution}</div>}
          {content.traceback && (
            <CodeBlock language="text" value={content.traceback} />
          )}
        </div>
      );
      break;

    case "tool_use":
      contentData = (
        <div>
          {content.name && <div>Tool: {content.name}</div>}
          <div>Input: {JSON.stringify(content.tool_input, null, 2)}</div>
          {content.output && (
            <div>Output: {JSON.stringify(content.output)}</div>
          )}
          {content.error && (
            <div className="text-red-500">
              Error: {JSON.stringify(content.error)}
            </div>
          )}
        </div>
      );
      break;

    case "media":
      contentData = (
        <div>
          {content.urls.map((url, index) => (
            <img
              key={index}
              src={url}
              alt={content.caption || `Media ${index}`}
            />
          ))}
          {content.caption && <div>{content.caption}</div>}
        </div>
      );
      break;
  }

  return (
    <div className="relative">
      {renderHeader}
      {renderDuration}
      {contentData}
    </div>
  );
}
