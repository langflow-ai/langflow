import { useCallback, useRef, useState } from "react";
import { ErrorBoundary } from "react-error-boundary";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";

// Type definitions for generative UI elements
interface GenerativeUIElement {
  type: "html" | "react" | "interactive";
  content: string;
  id?: string;
}

interface GenerativeUIRendererProps {
  content: string;
  onInteraction?: (action: string, data?: any) => void;
  className?: string;
}

// Error fallback component
function ErrorFallback({ error }: { error: Error }) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-md p-4 text-red-800">
      <div className="font-semibold">Rendering Error</div>
      <div className="text-sm mt-1">Failed to render generative UI content</div>
      <details className="mt-2 text-xs">
        <summary>Error details</summary>
        <pre className="mt-1 whitespace-pre-wrap">{error.message}</pre>
      </details>
    </div>
  );
}

// Component for rendering HTML content safely
function HTMLRenderer({
  content,
  onInteraction,
}: {
  content: string;
  onInteraction?: (action: string, data?: any) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  const handleClick = useCallback(
    (event: React.MouseEvent) => {
      const target = event.target as HTMLElement;

      // Handle button clicks
      if (target.tagName === "BUTTON" || target.closest("button")) {
        event.preventDefault();
        const button =
          target.tagName === "BUTTON" ? target : target.closest("button");
        const action = button?.getAttribute("data-action") || "button-click";
        const data = button?.getAttribute("data-value") || button?.textContent;
        onInteraction?.(action, data);
        return;
      }

      // Handle form submissions
      if (
        target.tagName === "INPUT" &&
        (target as HTMLInputElement).type === "submit"
      ) {
        event.preventDefault();
        const form = target.closest("form");
        const formData = new FormData(form as HTMLFormElement);
        const data = Object.fromEntries(formData);
        onInteraction?.("form-submit", data);
        return;
      }

      // Handle links
      if (target.tagName === "A" || target.closest("a")) {
        const link = target.tagName === "A" ? target : target.closest("a");
        const href = link?.getAttribute("href");
        if (href && !href.startsWith("http")) {
          event.preventDefault();
          onInteraction?.("navigate", { href });
          return;
        }
      }
    },
    [onInteraction],
  );

  return (
    <div
      ref={containerRef}
      onClick={handleClick}
      className="generative-ui-html-container"
      dangerouslySetInnerHTML={{ __html: content }}
    />
  );
}

// Component for rendering React-like JSX content
function ReactRenderer({
  content,
  onInteraction,
}: {
  content: string;
  onInteraction?: (action: string, data?: any) => void;
}) {
  // This is a simplified JSX-to-React converter for basic elements
  // In a real implementation, you might want to use a more robust JSX parser

  const parseJSX = (jsxString: string) => {
    try {
      // Remove JSX wrapper and extract the content
      const cleaned = jsxString.replace(/^<>\s*|\s*<\/>$/g, "").trim();

      // Simple JSX-like parsing for basic elements
      // This is a very basic implementation - you might want to use a proper JSX parser
      if (cleaned.includes("<Button")) {
        return parseButton(cleaned);
      }

      // Fallback to HTML renderer for complex JSX
      return <HTMLRenderer content={cleaned} onInteraction={onInteraction} />;
    } catch (error) {
      console.error("JSX parsing error:", error);
      return <div className="text-red-500">Error parsing JSX content</div>;
    }
  };

  const parseButton = (jsxString: string) => {
    const buttonMatch = jsxString.match(/<Button[^>]*>(.*?)<\/Button>/);
    if (buttonMatch) {
      const content = buttonMatch[1];
      const onClickMatch = jsxString.match(
        /onClick={[^}]*["']([^"']*)["'][^}]*}/,
      );
      const action = onClickMatch ? onClickMatch[1] : "button-click";

      return (
        <Button
          onClick={() => onInteraction?.(action, content)}
          className="mx-1 my-1"
        >
          {content}
        </Button>
      );
    }
    return null;
  };

  return (
    <div className="generative-ui-react-container">{parseJSX(content)}</div>
  );
}

// Main renderer component
export function GenerativeUIRenderer({
  content,
  onInteraction,
  className,
}: GenerativeUIRendererProps) {
  const [error, setError] = useState<string | null>(null);

  // Detect the type of content
  const detectContentType = (content: string): GenerativeUIElement => {
    const trimmed = content.trim();

    // Check for React JSX patterns
    if (
      trimmed.includes("onClick={") ||
      trimmed.match(/<[A-Z][a-zA-Z]*[^>]*>/)
    ) {
      return { type: "react", content: trimmed };
    }

    // Check for HTML with interactive elements
    if (
      trimmed.includes("<button") ||
      trimmed.includes("<form") ||
      trimmed.includes("data-action")
    ) {
      return { type: "interactive", content: trimmed };
    }

    // Check for HTML content
    if (trimmed.match(/<[a-z][^>]*>/) || trimmed.includes("</")) {
      return { type: "html", content: trimmed };
    }

    // Default to HTML if it looks like markup
    return { type: "html", content: trimmed };
  };

  const element = detectContentType(content);

  const renderContent = () => {
    switch (element.type) {
      case "react":
        return (
          <ReactRenderer
            content={element.content}
            onInteraction={onInteraction}
          />
        );
      case "interactive":
      case "html":
        return (
          <HTMLRenderer
            content={element.content}
            onInteraction={onInteraction}
          />
        );
      default:
        return <div>{element.content}</div>;
    }
  };

  if (error) {
    return <ErrorFallback error={new Error(error)} />;
  }

  return (
    <ErrorBoundary FallbackComponent={ErrorFallback}>
      <div className={cn("generative-ui-container", className)}>
        {renderContent()}
      </div>
    </ErrorBoundary>
  );
}

// Utility function to detect if content should be rendered as generative UI
export function isGenerativeUIContent(content: string): boolean {
  const trimmed = content.trim();

  // Check for HTML-like content
  if (trimmed.match(/<[a-zA-Z][^>]*>/)) {
    return true;
  }

  // Check for JSX-like content
  if (trimmed.includes("onClick={") || trimmed.match(/<[A-Z][a-zA-Z]*[^>]*>/)) {
    return true;
  }

  // Check for interactive markers
  if (
    trimmed.includes("data-action") ||
    trimmed.includes("<button") ||
    trimmed.includes("<form")
  ) {
    return true;
  }

  return false;
}

export default GenerativeUIRenderer;
