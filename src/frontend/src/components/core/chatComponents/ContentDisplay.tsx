import { ChevronDown } from "lucide-react";
import { type ReactNode, useState } from "react";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax/browser";
import remarkGfm from "remark-gfm";
import type { ContentType, JSONValue } from "@/types/chat";
import { extractLanguage, isCodeBlock } from "@/utils/codeBlockUtils";
import ForwardedIconComponent from "../../common/genericIconComponent";
import SimplifiedCodeTabComponent from "../codeTabsComponent";
import DurationDisplay from "./DurationDisplay";

export default function ContentDisplay({
  content,
  chatId,
  playgroundPage,
}: {
  content: ContentType;
  chatId: string;
  playgroundPage?: boolean;
}) {
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
            rehypePlugins={[rehypeMathjax]}
            className="markdown prose max-w-full text-sm font-normal dark:prose-invert"
            components={{
              a: ({ node, ...props }) => (
                <a {...props} target="_blank" rel="noopener noreferrer">
                  {props.children}
                </a>
              ),
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
                      return <span className="form-modal-markdown-span"></span>;
                    }
                  }

                  if (isCodeBlock(className, props, content)) {
                    return (
                      <SimplifiedCodeTabComponent
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
          <SimplifiedCodeTabComponent
            language="json"
            code={JSON.stringify(content.data, null, 2)}
          />
        </div>
      );
      break;

    case "error":
      contentData = (
        <div className="text-destructive">
          {content.reason && <div>Reason: {content.reason}</div>}
          {content.solution && <div>Solution: {content.solution}</div>}
          {content.traceback && (
            <SimplifiedCodeTabComponent
              language="text"
              code={content.traceback}
            />
          )}
        </div>
      );
      break;

    case "tool_use": {
      const formatToolOutput = (output: JSONValue) => {
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
                code: ({ node, className, children, ...props }) => {
                  const content = String(children);
                  if (isCodeBlock(className, props, content)) {
                    return (
                      <SimplifiedCodeTabComponent
                        language={extractLanguage(className)}
                        code={content.replace(/\n$/, "")}
                      />
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
            className="markdown prose max-w-full text-sm font-normal dark:prose-invert"
          >
            **Input:**
          </Markdown>
          <SimplifiedCodeTabComponent
            language="json"
            code={JSON.stringify(content.tool_input, null, 2)}
          />
          {content.output !== undefined && (
            <>
              <Markdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeMathjax]}
                className="markdown prose max-w-full text-sm font-normal dark:prose-invert"
              >
                **Output:**
              </Markdown>
              <div className="mt-1">{formatToolOutput(content.output)}</div>
            </>
          )}
          {content.error != null && (
            <div className="text-destructive">
              <Markdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeMathjax]}
                className="markdown prose max-w-full text-sm font-normal dark:prose-invert"
              >
                **Error:**
              </Markdown>
              <SimplifiedCodeTabComponent
                language="json"
                code={JSON.stringify(content.error, null, 2)}
              />
            </div>
          )}
        </div>
      );
      break;
    }

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

    case "image":
      contentData = (
        <div className="flex flex-col gap-2">
          {content.urls?.map((url, index) => (
            <img
              key={index}
              src={url}
              alt={content.caption || `Image ${index + 1}`}
              className="max-w-full rounded"
            />
          ))}
          {content.base64 && (
            <img
              src={`data:${content.mime_type || "image/png"};base64,${content.base64}`}
              alt={content.caption || "Image"}
              className="max-w-full rounded"
            />
          )}
          {content.caption && (
            <p className="text-xs text-muted-foreground">{content.caption}</p>
          )}
        </div>
      );
      break;

    case "audio":
      contentData = (
        <div className="flex flex-col gap-2">
          {content.urls?.map((url, index) => (
            <audio key={index} controls className="w-full">
              <source src={url} type={content.mime_type} />
            </audio>
          ))}
          {content.base64 && (
            <audio controls className="w-full">
              <source
                src={`data:${content.mime_type || "audio/mpeg"};base64,${content.base64}`}
                type={content.mime_type || "audio/mpeg"}
              />
            </audio>
          )}
          {content.transcript && (
            <p className="text-xs text-muted-foreground italic">
              {content.transcript}
            </p>
          )}
        </div>
      );
      break;

    case "video":
      contentData = (
        <div className="flex flex-col gap-2">
          {content.urls?.map((url, index) => (
            <video key={index} controls className="max-w-full rounded">
              <source src={url} type={content.mime_type} />
            </video>
          ))}
          {content.base64 && (
            <video controls className="max-w-full rounded">
              <source
                src={`data:${content.mime_type || "video/mp4"};base64,${content.base64}`}
                type={content.mime_type || "video/mp4"}
              />
            </video>
          )}
        </div>
      );
      break;

    case "file":
      contentData = (
        <div className="flex items-center gap-2">
          <ForwardedIconComponent
            name="File"
            className="h-4 w-4 text-muted-foreground"
          />
          {content.urls?.map((url, index) => (
            <a
              key={index}
              href={url}
              download={content.filename}
              className="text-sm underline text-primary hover:text-primary/80"
              target="_blank"
              rel="noopener noreferrer"
            >
              {content.filename || `Download file ${index + 1}`}
            </a>
          ))}
        </div>
      );
      break;

    case "reasoning":
      contentData = <ReasoningDisplay text={content.text} />;
      break;

    case "usage":
      contentData = (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {content.model && (
            <span className="font-medium">{content.model}</span>
          )}
          <span>
            Tokens:{" "}
            {content.input_tokens !== undefined
              ? `${content.input_tokens} in`
              : ""}
            {content.input_tokens !== undefined &&
            content.output_tokens !== undefined
              ? " / "
              : ""}
            {content.output_tokens !== undefined
              ? `${content.output_tokens} out`
              : ""}
          </span>
        </div>
      );
      break;

    case "citation":
      contentData = (
        <div className="flex flex-col gap-1 text-sm">
          {content.url ? (
            <a
              href={content.url}
              target="_blank"
              rel="noopener noreferrer"
              className="underline text-primary hover:text-primary/80"
            >
              {content.title || content.url}
            </a>
          ) : (
            content.title && (
              <span className="font-medium">{content.title}</span>
            )
          )}
          {content.cited_text && (
            <blockquote className="border-l-2 border-muted-foreground/30 pl-3 text-xs text-muted-foreground italic">
              {content.cited_text}
            </blockquote>
          )}
        </div>
      );
      break;
  }

  return (
    <div className="relative p-[16px]">
      {renderDuration}
      {contentData}
    </div>
  );
}

/** Collapsible "Thinking" section for reasoning content. */
function ReasoningDisplay({ text }: { text: string }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
      >
        <ChevronDown
          className={`h-3 w-3 transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
        Thinking
      </button>
      {isOpen && (
        <div className="pl-4 text-xs text-muted-foreground whitespace-pre-wrap border-l-2 border-muted-foreground/20">
          {text}
        </div>
      )}
    </div>
  );
}
