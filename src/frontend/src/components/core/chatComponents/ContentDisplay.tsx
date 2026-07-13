import { ChevronDown } from "lucide-react";
import { Fragment, type ReactNode, useState } from "react";
import Markdown from "react-markdown";
import rehypeMathjax from "rehype-mathjax/browser";
import remarkGfm from "remark-gfm";
import { formatSeconds } from "@/components/core/playgroundComponent/chat-view/chat-messages/utils/format";
import type {
  ContentBlockItem,
  ContentType,
  InteractiveContent,
  JSONValue,
} from "@/types/chat";
import { extractLanguage, isCodeBlock } from "@/utils/codeBlockUtils";
import ForwardedIconComponent from "../../common/genericIconComponent";
import SimplifiedCodeTabComponent from "../codeTabsComponent";
import DurationDisplay from "./DurationDisplay";
import HumanInputCard, { type HumanInputDecision } from "./HumanInputCard";
import {
  AudioContentDisplay,
  FileContentDisplay,
  ImageContentDisplay,
  VideoContentDisplay,
} from "./MediaContentDisplay";
import { SourcesStrip } from "./SourcesStrip";
import { ToolOutputDisplay } from "./ToolOutputDisplay";
import { ToolSection } from "./ToolSection";
import { safeUrl } from "./url";

export default function ContentDisplay({
  content,
  chatId,
  playgroundPage,
  humanInputSubmitted,
  onHumanInputSubmit,
}: {
  // Accept any ContentBlockItem so nested ContentBlock groups land in the
  // `case "group"` branch below instead of falling through to no rendering.
  content: ContentBlockItem;
  chatId: string;
  playgroundPage?: boolean;
  humanInputSubmitted?: boolean;
  onHumanInputSubmit?: (
    content: InteractiveContent,
    decision: HumanInputDecision,
  ) => void;
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
      // Tool output rendering lives in ToolOutputDisplay — it routes by
      // shape (markdown string / preformatted text / object) and, when
      // the producer hands us a LangChain ToolMessage envelope with
      // non-standard metadata (additional_kwargs, response_metadata,
      // artifact, ...), surfaces it under a 2-tab UI so the readable
      // content stays primary and the plumbing is one click away.

      // Backend serializes ToolContent.tool_input under its alias `input`
      // when by_alias=True (AG-UI emission, certain dump paths). Prefer
      // the field name, fall back to the alias so already-stored messages
      // and live AG-UI events both render their arguments.
      const toolInput = content.tool_input ?? content.input ?? {};
      const hasInput = Object.keys(toolInput).length > 0;
      // Treat an empty (or whitespace-only) string as "no output" so it
      // doesn't render an empty bordered box. Legitimate falsy outputs like
      // 0 or false still render through ToolOutputDisplay.
      const hasOutput =
        content.output !== undefined &&
        content.output !== null &&
        !(typeof content.output === "string" && content.output.trim() === "");
      const hasError = content.error != null;
      // Each section carries an eyebrow label (Arguments / Error) so the
      // parts of a tool call read clearly inside the accordion card. The
      // output section renders through ToolOutputDisplay, which supplies its
      // own Result/Metadata tabs, and a hairline rule separates the input
      // from the result. Empty sections render nothing.
      const showSeparator = hasInput && (hasOutput || hasError);
      contentData = (
        <div className="flex flex-col gap-3">
          {hasInput && (
            <ToolSection eyebrow="Arguments">
              <ToolInputDisplay input={toolInput} />
            </ToolSection>
          )}
          {showSeparator && <div className="h-px bg-border" />}
          {hasOutput && (
            <ToolOutputDisplay output={content.output as JSONValue} />
          )}
          {hasError && (
            <ToolSection eyebrow="Error">
              <div className="rounded-md bg-destructive/10 text-destructive">
                <SimplifiedCodeTabComponent
                  language="json"
                  code={JSON.stringify(content.error, null, 2)}
                />
              </div>
            </ToolSection>
          )}
        </div>
      );
      break;
    }

    case "media":
      contentData = (
        <div>
          {content.urls.map((url, index) => {
            const src = safeUrl(url);
            if (!src) return null;
            return (
              <img
                key={index}
                src={src}
                alt={content.caption || `Media ${index}`}
              />
            );
          })}
          {content.caption && <div>{content.caption}</div>}
        </div>
      );
      break;

    case "image":
      contentData = <ImageContentDisplay content={content} />;
      break;

    case "audio":
      contentData = <AudioContentDisplay content={content} />;
      break;

    case "video":
      contentData = <VideoContentDisplay content={content} />;
      break;

    case "file":
      contentData = <FileContentDisplay content={content} />;
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
    case "human_input":
      contentData = (
        <HumanInputCard
          content={content}
          submitted={humanInputSubmitted}
          onSubmit={
            onHumanInputSubmit
              ? (decision) => onHumanInputSubmit(content, decision)
              : undefined
          }
        />
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
