import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeMathjax from "rehype-mathjax";
import rehypeRaw from "rehype-raw";
import { preprocessChatMessage } from "@/utils/markdownUtils";
import { EMPTY_OUTPUT_SEND_MESSAGE } from "@/constants/constants";
import CodeTabsComponent from "@/components/core/codeTabsComponent";
import { Message } from "./Playground.types";
import { Button } from "@/components/ui/button";
import { File, Eye } from "lucide-react";

interface MessageRendererProps {
  message: Message;
  displayedTexts: Map<string, string>;
  targetTexts: Map<string, string>;
  loadingDots: number;
  onPreviewAttachment?: (file: {
    url: string;
    name: string;
    type: string;
  }) => void;
}

// Helper function to strip markdown code fences
const stripCodeFence = (text: string): string => {
  const trimmed = text.trim();

  // Match ```json ... ``` or ``` ... ```
  const codeFenceMatch = trimmed.match(/^```(?:json)?\s*\n?([\s\S]*?)\n?```$/);
  if (codeFenceMatch) {
    return codeFenceMatch[1].trim();
  }

  return text;
};

// Helper function to check if text is JSON
const isJsonString = (str: string): boolean => {
  if (!str || typeof str !== "string") return false;

  const trimmed = str.trim();
  if (!trimmed) return false;

  if (
    (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
    (trimmed.startsWith("[") && trimmed.endsWith("]"))
  ) {
    try {
      JSON.parse(trimmed);
      return true;
    } catch {
      return false;
    }
  }
  return false;
};

// Helper function to format JSON
const formatJson = (jsonString: string): string => {
  try {
    const parsed = JSON.parse(jsonString);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return jsonString;
  }
};

export function MessageRenderer({
  message,
  displayedTexts,
  targetTexts,
  loadingDots,
  onPreviewAttachment,
}: MessageRendererProps) {
  const renderMessageContent = () => {
    if (message.type === "agent") {
      const displayedText = displayedTexts.get(message.id);

      // Use displayed text if available, otherwise use message.text
      let textToRender: string;
      if (displayedText !== undefined) {
        textToRender = displayedText || `Working${".".repeat(loadingDots)}`;
      } else {
        textToRender = message.text || "";
      }

      // If streaming is complete and we have message.text, always use that
      if (!message.isStreaming && message.text) {
        textToRender = message.text;
      }

      // Strip markdown code fence and check if it's JSON
      const strippedText = stripCodeFence(textToRender);

      if (isJsonString(strippedText)) {
        const formattedJson = formatJson(strippedText);
        return (
          <div className="relative w-full">
            <div className="absolute top-2 right-2 z-10">
              <button
                onClick={() => navigator.clipboard?.writeText(formattedJson)}
                className="px-3 py-1.5 text-xs bg-white hover:bg-gray-50 border border-gray-300 rounded transition-colors shadow-sm font-medium"
                title="Copy JSON"
              >
                Copy
              </button>
            </div>
            <pre className="bg-gray-50 p-4 pr-20 rounded-md overflow-x-auto text-xs font-mono border border-gray-200 max-h-[600px] overflow-y-auto">
              <code className="text-gray-800">{formattedJson}</code>
            </pre>
          </div>
        );
      }

      // Render rich Markdown like Langflow's ChatMessage
      const processedChatMessage = preprocessChatMessage(textToRender);

      return (
        <Markdown
          remarkPlugins={[remarkGfm as any]}
          linkTarget="_blank"
          rehypePlugins={[rehypeMathjax, rehypeRaw]}
          className="markdown prose flex w-full max-w-full flex-col items-baseline text-sm font-normal word-break-break-word dark:prose-invert"
          components={{
            p({ node, ...props }) {
              return (
                <p className="w-fit max-w-full my-1.5 last:mb-0 first:mt-0">
                  {props.children}
                </p>
              );
            },
            ol({ node, ...props }) {
              return <ol className="max-w-full">{props.children}</ol>;
            },
            ul({ node, ...props }) {
              return <ul className="max-w-full mb-2">{props.children}</ul>;
            },
            pre({ node, ...props }) {
              return <>{props.children}</>;
            },
            hr({ node, ...props }) {
              return (
                <hr className="w-full mt-3 mb-5 border-border" {...props} />
              );
            },
            h3({ node, ...props }) {
              return (
                <h3 className={"mt-4 " + (props.className || "")} {...props} />
              );
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

                  // Specifically handle <think> tags wrapped in backticks
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
          {processedChatMessage.trim().length === 0 && !message.isStreaming
            ? EMPTY_OUTPUT_SEND_MESSAGE
            : processedChatMessage}
        </Markdown>
      );
    }

    return (
      <div className="whitespace-pre-wrap break-words">{message.text}</div>
    );
  };

  const showCursor = () => {
    if (message.isStreaming && message.type === "agent") {
      const displayedText = displayedTexts.get(message.id) || "";
      const targetText = targetTexts.get(message.id) || message.text;
      return (
        displayedText &&
        displayedText.length > 0 &&
        displayedText.length <= targetText.length
      );
    }
    return false;
  };

  const shouldShowTimestamp = () => {
    if (message.type === "user") {
      return true;
    }

    if (message.type === "agent") {
      const displayedText = displayedTexts.get(message.id);

      if (displayedText !== undefined && displayedText.length > 0) {
        return true;
      }

      if (displayedText === undefined && message.text) {
        return true;
      }

      return false;
    }

    return false;
  };

  return (
    <div className="space-y-2">
      <div
        className={`flex ${
          message.type === "user" ? "justify-end" : "justify-start"
        }`}
      >
        <div
          className={`max-w-[85%] rounded-lg  ${
            message.type === "user"
              ? "bg-[#F5F2FF] text-[#64616A] p-2"
              : " text-[#444]"
          }`}
        >
          <div className="break-words">
            {renderMessageContent()}
            {showCursor() && (
              <span className="inline-block w-0.5 h-5 ml-0.5 bg-foreground animate-pulse"></span>
            )}
          </div>

          {/* Attachments preview chips */}
          {message.files && message.files.length > 0 && (
            <div
              className={`mt-3 flex flex-wrap gap-2 ${
                message.type === "user" ? "text-white" : "text-[#444]"
              }`}
            >
              {message.files.map((f, idx) => (
                <div
                  key={`${f.url}-${idx}`}
                  className={`flex items-center gap-2 ${
                    message.type === "user" ? "bg-[#4C23A6]" : "bg-white"
                  } border rounded-lg px-3 py-2 text-sm group ${
                    message.type === "user"
                      ? "border-white/20"
                      : "border-gray-200"
                  }`}
                >
                  <File className="h-4 w-4 flex-shrink-0" />
                  <span className="truncate max-w-[200px]" title={f.name}>
                    {f.name}
                  </span>
                  {onPreviewAttachment && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        onPreviewAttachment({
                          url: f.url,
                          name: f.name,
                          type: f.type,
                        })
                      }
                      className={`h-6 w-6 p-0 ml-1 ${
                        message.type === "user"
                          ? "text-white hover:text-white/90"
                          : "text-muted-foreground hover:text-primary"
                      }`}
                      title="Preview file"
                    >
                      <Eye className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {shouldShowTimestamp() && (
        <div
          className={`flex text-xs text-muted-foreground ${
            message.type === "user" ? "justify-end" : "justify-start"
          }`}
        >
          <span className="px-4">{message.timestamp.toLocaleTimeString()}</span>
        </div>
      )}
    </div>
  );
}
