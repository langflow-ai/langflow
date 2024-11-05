import { CodeBlock } from "@/modals/IOModal/components/chatView/chatMessage/codeBlock";
import { ReactNode } from "react";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax";
import remarkGfm from "remark-gfm";
import SimplifiedCodeTabComponent from "../codeTabsComponent/ChatCodeTabComponent";
import DurationDisplay from "./DurationDisplay";

export default function ContentDisplay({
  type,
  content,
}: {
  type: string;
  content: any;
}) {
  let contentData: ReactNode | null = null;

  if (type === "title") {
    return <div>{content}</div>;
  }
  if (type === "duration") {
    contentData = (
      <div className="absolute right-0 top-2">
        <DurationDisplay duration={content} />
      </div>
    );
  }
  if (typeof content === "object") {
    // returning directly to avoid object object render
    const stringValue = JSON.stringify(content, null, 2);
    return (
      <div key={type}>
        <span className="font-bold capitalize">{type}</span>
        :
        <CodeBlock language="json" value={stringValue} />
      </div>
    );
  }

  contentData = (
    <div className="ml-1">
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
        {String(content)}
      </Markdown>
    </div>
  );

  return (
    <div key={type}>
      <span className="font-bold capitalize">{type}</span>:{contentData}
    </div>
  );
}
