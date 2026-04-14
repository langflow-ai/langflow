import { useEffect, useMemo, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import langflowAssistantIcon from "@/assets/langflow_assistant.svg";
import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import { CustomProfileIcon } from "@/customization/components/custom-profile-icon";
import { extractLanguage, isCodeBlock } from "@/utils/codeBlockUtils";
import { cn } from "@/utils/utils";
import type { AssistantMessage } from "../assistant-panel.types";
import { getRandomThinkingMessage } from "../helpers/messages";
import { AssistantComponentResult } from "./assistant-component-result";
import { AssistantLoadingState } from "./assistant-loading-state";
import { AssistantValidationFailed } from "./assistant-validation-failed";

interface AssistantMessageItemProps {
  message: AssistantMessage;
  onApprove?: (messageId: string, componentCode?: string) => void;
  onRetry?: (messageId: string) => void;
}

function ThinkingIndicator({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-3 text-sm text-muted-foreground">
      <span className="flex gap-1">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-muted-foreground" />
        <span
          className="h-1.5 w-1.5 animate-pulse rounded-full bg-muted-foreground"
          style={{ animationDelay: "150ms" }}
        />
        <span
          className="h-1.5 w-1.5 animate-pulse rounded-full bg-muted-foreground"
          style={{ animationDelay: "300ms" }}
        />
      </span>
      <span>{message}</span>
    </div>
  );
}

export function AssistantMessageItem({
  message,
  onApprove,
  onRetry,
}: AssistantMessageItemProps) {
  const isUser = message.role === "user";
  const isStreaming = message.status === "streaming";
  const hasValidatedResult =
    message.result?.validated && message.result?.componentCode;
  const hasValidationError =
    message.result?.validated === false && message.result?.validationError;
  // Skip animation if the message is already complete on mount (e.g. panel was closed and reopened)
  const [validationAnimationComplete, setValidationAnimationComplete] =
    useState(message.status === "complete");

  // Timeout fallback: if message is complete but user hasn't clicked Continue,
  // force transition after 30s to prevent indefinitely stuck loading states
  useEffect(() => {
    if (
      message.status === "complete" &&
      (hasValidatedResult || hasValidationError) &&
      !validationAnimationComplete
    ) {
      const timer = setTimeout(() => {
        setValidationAnimationComplete(true);
      }, 30000);
      return () => clearTimeout(timer);
    }
  }, [
    message.status,
    hasValidatedResult,
    hasValidationError,
    validationAnimationComplete,
  ]);

  // Generate randomized messages once per message
  const thinkingMessage = useMemo(() => getRandomThinkingMessage(), []);

  // Steps that indicate component generation mode (not just Q&A)
  const componentGenerationSteps = [
    "generating_component",
    "extracting_code",
    "validating",
    "validation_failed",
    "retrying",
    "validated",
  ];

  // Detect component code in streaming content (handles misclassified intent)
  const contentLooksLikeComponentCode =
    isStreaming &&
    message.content &&
    /```python[\s\S]*class\s+\w+.*Component/.test(message.content);

  // Check if we're in component generation mode
  const isComponentGeneration =
    (message.progress &&
      componentGenerationSteps.includes(message.progress.step)) ||
    contentLooksLikeComponentCode;

  // Show loading state during component generation
  const isGeneratingCode = isStreaming && isComponentGeneration;

  const renderContent = () => {
    // Show detailed loading state during component generation
    // Keep showing it until validation animation completes
    const showLoadingState =
      (isGeneratingCode && message.progress) ||
      ((hasValidatedResult || hasValidationError) &&
        !validationAnimationComplete &&
        message.progress);

    if (showLoadingState && message.progress) {
      return (
        <AssistantLoadingState
          key={message.id}
          progress={message.progress}
          streamingContent={message.content}
          onValidationComplete={() => setValidationAnimationComplete(true)}
        />
      );
    }

    // Show connection/request error
    if (message.status === "error" && message.error) {
      return (
        <p className="text-sm font-normal text-destructive">{message.error}</p>
      );
    }

    // Show cancelled state
    if (message.status === "cancelled") {
      return (
        <span className="text-sm text-muted-foreground/60 italic">
          Cancelled
        </span>
      );
    }

    // Show validation failure after all retries (only after animation completes)
    const canShowResult = validationAnimationComplete || !message.progress;
    if (hasValidationError && message.result && canShowResult) {
      return (
        <AssistantValidationFailed
          result={message.result}
          onRetry={onRetry ? () => onRetry(message.id) : undefined}
        />
      );
    }

    // Show successful component result (only after validation animation completes, or if no animation was needed)
    if (hasValidatedResult && message.result && canShowResult) {
      return (
        <AssistantComponentResult
          result={message.result}
          onApprove={() => onApprove?.(message.id)}
        />
      );
    }

    // Fallback: component generation where backend returned code in the response
    // text but didn't set result.validated (e.g., code extraction format mismatch).
    // Only applies when the message has progress steps from component generation,
    // NOT for plain Q&A responses that happen to contain example code.
    const wasComponentGeneration = message.completedSteps?.some((step) =>
      [
        "generating_component",
        "extracting_code",
        "validating",
        "validated",
      ].includes(step),
    );
    if (wasComponentGeneration && message.status === "complete") {
      const componentCodeMatch = message.content?.match(
        /```python\s*\n([\s\S]*?class\s+(\w+)\s*\(.*Component.*\)[\s\S]*?)```/,
      );
      if (componentCodeMatch) {
        const extractedCode = componentCodeMatch[1];
        const extractedClassName = componentCodeMatch[2];
        return (
          <AssistantComponentResult
            result={{
              content: message.content,
              validated: true,
              componentCode: extractedCode,
              className: extractedClassName,
            }}
            onApprove={() => onApprove?.(message.id, extractedCode)}
          />
        );
      }
    }

    // Default text content with markdown support
    return (
      <Markdown
        remarkPlugins={[remarkGfm]}
        className="prose prose-sm max-w-full text-muted-foreground dark:prose-invert prose-p:leading-relaxed prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5"
        components={{
          a: ({ node, ...props }) => (
            <a
              {...props}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline"
            >
              {props.children}
            </a>
          ),
          p({ node, ...props }) {
            return <p className="my-1">{props.children}</p>;
          },
          pre({ node, ...props }) {
            return <>{props.children}</>;
          },
          code: ({ node, className, children, ...props }) => {
            const content = String(children);
            if (isCodeBlock(className, props, content)) {
              return (
                <SimplifiedCodeTabComponent
                  language={extractLanguage(className, content)}
                  code={content.replace(/\n$/, "")}
                  maxHeight={isStreaming ? "200px" : undefined}
                />
              );
            }
            return (
              <code className="rounded bg-muted px-1 py-0.5 text-sm" {...props}>
                {children}
              </code>
            );
          },
        }}
      >
        {message.content}
      </Markdown>
    );
  };

  // Show simple thinking when:
  // 1. Streaming without content yet (both Q&A and component generation)
  // 2. Component generation in early phase (before extraction/validation)
  const isSimpleThinking = isStreaming && !isGeneratingCode && !message.content;

  if (isSimpleThinking && !isUser) {
    return (
      <div className="mb-6 mt-4">
        <ThinkingIndicator message={thinkingMessage} />
      </div>
    );
  }

  return (
    <div className="mb-6" data-testid={`assistant-message-${message.role}`}>
      <div className="flex items-start gap-3">
        {isUser ? (
          <CustomProfileIcon className="h-7 w-7 shrink-0 rounded-full" />
        ) : (
          <div className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-lg">
            <img
              src={langflowAssistantIcon}
              alt="Langflow Assistant"
              className="h-full w-full object-cover"
            />
          </div>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <span
            className={cn(
              "text-[13px] font-semibold leading-4",
              isUser ? "text-foreground" : "text-accent-pink-foreground",
            )}
          >
            {isUser ? "User" : "Langflow Assistant"}
          </span>
          <div className="mt-3 overflow-hidden">{renderContent()}</div>
        </div>
      </div>
    </div>
  );
}
