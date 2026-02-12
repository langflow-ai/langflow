import { useContext, useMemo, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import langflowAssistantIcon from "@/assets/langflow_assistant.svg";
import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import { AuthContext } from "@/contexts/authContext";
import { BASE_URL_API } from "@/customization/config-constants";
import { extractLanguage, isCodeBlock } from "@/utils/codeBlockUtils";
import { cn } from "@/utils/utils";
import type { AssistantMessage } from "../assistant-panel.types";
import { getRandomThinkingMessage } from "../helpers/messages";
import { AssistantComponentResult } from "./assistant-component-result";
import { AssistantLoadingState } from "./assistant-loading-state";
import { AssistantValidationFailed } from "./assistant-validation-failed";

interface AssistantMessageItemProps {
  message: AssistantMessage;
  onApprove?: (messageId: string) => void;
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
}: AssistantMessageItemProps) {
  const { userData } = useContext(AuthContext);
  const isUser = message.role === "user";
  const isStreaming = message.status === "streaming";
  const hasValidatedResult =
    message.result?.validated && message.result?.componentCode;
  const hasValidationError =
    message.result?.validated === false && message.result?.validationError;
  const [validationAnimationComplete, setValidationAnimationComplete] =
    useState(false);

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

  // Check if we're in component generation mode
  const isComponentGeneration =
    message.progress &&
    componentGenerationSteps.includes(message.progress.step);

  // Show loading state during component generation
  const isGeneratingCode = isStreaming && isComponentGeneration;

  const profileImageUrl = `${BASE_URL_API}files/profile_pictures/${
    userData?.profile_image ?? "Space/046-rocket.svg"
  }`;

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
          completedSteps={message.completedSteps || []}
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
      return <AssistantValidationFailed result={message.result} />;
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
    <div className="mb-6">
      <div className="flex items-start gap-3">
        {isUser ? (
          <img
            src={profileImageUrl}
            alt="User"
            className="h-7 w-7 shrink-0 rounded-full"
          />
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
