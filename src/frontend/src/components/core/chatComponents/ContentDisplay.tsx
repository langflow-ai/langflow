import { ChevronDown } from "lucide-react";
import { Fragment, type ReactNode, useState } from "react";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax/browser";
import remarkGfm from "remark-gfm";
import { formatSeconds } from "@/components/core/playgroundComponent/chat-view/chat-messages/utils/format";
import type { ContentBlockItem, JSONValue } from "@/types/chat";
import { extractLanguage, isCodeBlock } from "@/utils/codeBlockUtils";
import ForwardedIconComponent from "../../common/genericIconComponent";
import SimplifiedCodeTabComponent from "../codeTabsComponent";
import DurationDisplay from "./DurationDisplay";
import { SourcesStrip } from "./SourcesStrip";
import { looksPreformatted, unwrapToolMessage } from "./toolOutput";

export default function ContentDisplay({
  content,
  chatId,
  playgroundPage,
}: {
  // Accept any ContentBlockItem so nested ContentBlock groups land in the
  // `case "group"` branch below instead of falling through to no rendering.
  content: ContentBlockItem;
  chatId: string;
  playgroundPage?: boolean;
}) {
  // Reasoning blocks surface their own duration inline via ReasoningDisplay's
  // "Thought for Xs" label, so skip the absolute top-right DurationDisplay
  // there to avoid rendering the same duration twice.
  const renderDuration = content.duration !== undefined &&
    content.type !== "reasoning" &&
    !playgroundPage && (
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
      // Tool output rendering routes by the *unwrapped* payload shape:
      //   - markdown-y string  -> Markdown renderer (prose, no chrome)
      //   - pre-formatted text -> code tab with language=text
      //                           (monospace, contained horizontal scroll,
      //                           built-in copy button)
      //   - object / array     -> code tab with language=json (same)
      // The LangChain ToolMessage envelope is unwrapped first so the
      // readable `content` field becomes the body and the plumbing
      // metadata (already shown by the accordion trigger) stays hidden.
      const formatToolOutput = (raw: JSONValue) => {
        const output = unwrapToolMessage(raw);
        if (output === null || output === undefined) return null;

        if (typeof output === "string") {
          if (looksPreformatted(output)) {
            return <SimplifiedCodeTabComponent language="text" code={output} />;
          }
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

      // Backend serializes ToolContent.tool_input under its alias `input`
      // when by_alias=True (AG-UI emission, certain dump paths). Prefer
      // the field name, fall back to the alias so already-stored messages
      // and live AG-UI events both render their arguments.
      const toolInput = content.tool_input ?? content.input ?? {};
      const hasInput = Object.keys(toolInput).length > 0;
      // Treat an empty (or whitespace-only) string as "no output" so it
      // doesn't render an empty bordered box. Legitimate falsy outputs like
      // 0 or false still render through formatToolOutput.
      const hasOutput =
        content.output !== undefined &&
        content.output !== null &&
        !(typeof content.output === "string" && content.output.trim() === "");
      const hasError = content.error != null;
      // Eyebrow labels (INPUT/OUTPUT/ERROR) used to bracket each section,
      // but the surrounding accordion card is already the "tool call"
      // context — extra labels just add chrome. Match the assistant-ui /
      // Claude pattern: args and result stack directly inside the card,
      // separated by a hairline rule. Empty sections render nothing.
      const showSeparator = hasInput && (hasOutput || hasError);
      contentData = (
        <div className="flex flex-col gap-3">
          {hasInput && <ToolInputDisplay input={toolInput} />}
          {showSeparator && <div className="h-px bg-border" />}
          {hasOutput && (
            <div className="max-h-96 overflow-auto">
              {formatToolOutput(content.output as JSONValue)}
            </div>
          )}
          {hasError && (
            <div className="rounded-md bg-destructive/10 text-destructive">
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
          {/* base64 is a fallback for when no usable URL is provided.
              `some(Boolean)` so urls=[""] or urls=[null] don't suppress the
              fallback while rendering a broken <img src=""> above. */}
          {!content.urls?.some(Boolean) && content.base64 && (
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
          {!content.urls?.some(Boolean) && content.base64 && (
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
          {!content.urls?.some(Boolean) && content.base64 && (
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
      contentData = (
        <ReasoningDisplay text={content.text} duration={content.duration} />
      );
      break;

    case "usage": {
      // Backend serializes Optional[int] as JSON null, so `!= null` catches
      // both undefined and null. Using `!== undefined` here would render the
      // literal string "null in / null out" when the producer reports no
      // counts.
      const hasInput = content.input_tokens != null;
      const hasOutput = content.output_tokens != null;
      const hasTokens = hasInput || hasOutput;
      contentData = (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {content.model && (
            <span className="font-medium">{content.model}</span>
          )}
          {hasTokens && (
            <span>
              Tokens: {hasInput ? `${content.input_tokens} in` : ""}
              {hasInput && hasOutput ? " / " : ""}
              {hasOutput ? `${content.output_tokens} out` : ""}
            </span>
          )}
        </div>
      );
      break;
    }

    case "citation":
      // Single citation renders as a one-card Sources strip; consecutive
      // flat citations are coalesced into a multi-card strip by
      // ContentBlockDisplay before they reach this branch.
      contentData = <SourcesStrip citations={[content]} />;
      break;

    case "group":
      // A nested ContentBlock inside another container. Render the title as
      // a small section header and recurse on each child. The outer
      // ContentBlockDisplay handles top-level groups; this branch only
      // fires when a producer nests a group inside a parent's contents.
      contentData = (
        <div className="flex flex-col gap-2">
          {content.title && (
            <p className="text-sm font-medium text-primary">{content.title}</p>
          )}
          {content.contents?.map((child, index) => (
            <ContentDisplay
              key={index}
              content={child}
              chatId={`${chatId}-${index}`}
              playgroundPage={playgroundPage}
            />
          ))}
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

/** Renders a tool's input. Flat objects (string/number/bool/null values
 * only) become labelled rows; anything nested falls back to a JSON block
 * so the structure stays readable. Empty input is handled by the caller
 * (the surrounding card simply skips this component). */
function ToolInputDisplay({ input }: { input: Record<string, JSONValue> }) {
  const entries = Object.entries(input);
  // A value counts as "flat" if it's a primitive or a list of primitives.
  // Nested objects (or arrays of objects) fall through to the JSON block
  // where indentation makes them readable.
  const isPrimitive = (v: JSONValue) => v === null || typeof v !== "object";
  const isFlat = entries.every(
    ([, v]) => isPrimitive(v) || (Array.isArray(v) && v.every(isPrimitive)),
  );
  if (!isFlat) {
    return (
      <SimplifiedCodeTabComponent
        language="json"
        code={JSON.stringify(input, null, 2)}
      />
    );
  }
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
      {entries.map(([key, value]) => (
        <Fragment key={key}>
          <dt className="font-mono text-muted-foreground">{key}</dt>
          <dd className="font-mono break-all">{JSON.stringify(value)}</dd>
        </Fragment>
      ))}
    </dl>
  );
}

/** Reasoning section. Live shimmer while streaming, collapsible summary once
 * the producer attaches a `duration` (its signal that the step is done). */
function ReasoningDisplay({
  text,
  duration,
}: {
  text: string;
  duration?: number;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const isStreaming = duration === undefined;

  if (isStreaming) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <ForwardedIconComponent
          name="Sparkles"
          className="h-3 w-3"
          aria-hidden
        />
        <span className="animate-pulse">Thinking…</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground w-fit"
      >
        <ForwardedIconComponent
          name="Sparkles"
          className="h-3 w-3"
          aria-hidden
        />
        <span>Thought for {formatSeconds(duration)}</span>
        <ChevronDown
          className={`h-3 w-3 transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </button>
      {isOpen && (
        <div className="ml-1 pl-3 text-xs text-muted-foreground whitespace-pre-wrap border-l-2 border-muted-foreground/20 italic">
          {text}
        </div>
      )}
    </div>
  );
}
