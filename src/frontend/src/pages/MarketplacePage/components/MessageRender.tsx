import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { hasMarkdownFormatting } from "@/utils/markdownUtils";
import { Message } from "./Playground.types";

interface MessageRendererProps {
  message: Message;
  displayedTexts: Map<string, string>;
  targetTexts: Map<string, string>;
  loadingDots: number;
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
  if (!str || typeof str !== 'string') return false;
  
  const trimmed = str.trim();
  if (!trimmed) return false;
  
  if (
    (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
    (trimmed.startsWith('[') && trimmed.endsWith(']'))
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

      // Check if it has markdown formatting (original text with code fences)
      if (hasMarkdownFormatting(textToRender)) {
        return (
          <Markdown
            remarkPlugins={[remarkGfm]}
            className="prose prose-sm dark:prose-invert max-w-none"
          >
            {textToRender}
          </Markdown>
        );
      }
      
      // Default to whitespace-preserved text
      return <div className="whitespace-pre-wrap break-words">{textToRender}</div>;
    }
    
    return <div className="whitespace-pre-wrap break-words">{message.text}</div>;
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
          className={`max-w-[85%] rounded-lg px-4 py-3 ${
            message.type === "user"
              ? "bg-[#350E84] text-white"
              : "bg-[#F8F9FA] text-[#444] border border-gray-200"
          }`}
        >
          <div className="break-words">
            {renderMessageContent()}
            {showCursor() && (
              <span className="inline-block w-0.5 h-5 ml-0.5 bg-foreground animate-pulse"></span>
            )}
          </div>
        </div>
      </div>

      {shouldShowTimestamp() && (
        <div
          className={`flex text-xs text-muted-foreground ${
            message.type === "user" ? "justify-end" : "justify-start"
          }`}
        >
          <span className="px-4">
            {message.timestamp.toLocaleTimeString()}
          </span>
        </div>
      )}
    </div>
  );
}