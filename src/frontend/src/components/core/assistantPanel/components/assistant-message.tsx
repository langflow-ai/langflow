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
import { AssistantFileCard } from "./assistant-file-card";
import { FlowEditCarousel } from "./assistant-flow-edit-card";
import { AssistantFlowPreview } from "./assistant-flow-preview";
import { AssistantLoadingState } from "./assistant-loading-state";
import { AssistantValidationFailed } from "./assistant-validation-failed";
import { FileContentModal } from "./file-content-modal";

interface AssistantMessageItemProps {
  message: AssistantMessage;
  onApprove?: (messageId: string) => void;
  onUpdateFlowAction?: (
    messageId: string,
    actionId: string,
    status: "applied" | "dismissed",
  ) => void;
  onApplyFlowProposal?: (messageId: string) => void;
  onDismissFlowProposal?: (messageId: string) => void;
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
  onUpdateFlowAction,
  onApplyFlowProposal,
  onDismissFlowProposal,
  onRetry,
}: AssistantMessageItemProps) {
  const isUser = message.role === "user";
  const isStreaming = message.status === "streaming";
  const hasValidatedResult =
    message.result?.validated && message.result?.componentCode;
  const hasValidationError =
    message.result?.validated === false && message.result?.validationError;
  const hasWrittenFiles = (message.writtenFiles?.length ?? 0) > 0;
  const [validationAnimationComplete, setValidationAnimationComplete] =
    useState(false);
  // Modal state for "Open" on a file card. Single-modal-at-a-time per message
  // so the user always has clear focus on which file they're inspecting.
  const [openFilePath, setOpenFilePath] = useState<string | null>(null);

  // Timeout fallback: if message is complete but user hasn't clicked Continue,
  // force transition after 30s to prevent indefinitely stuck loading states.
  // Only applies to the component-generation path — documents render their
  // final state directly without a Continue gate.
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

  // Generate randomized messages once per message. For manage_files we
  // override the random label with the static "Generating document..." so
  // the thinking dots match the input placeholder (no rotating noise).
  const randomThinking = useMemo(() => getRandomThinkingMessage(), []);
  const thinkingMessage =
    message.progress?.step === "generating_document"
      ? message.progress.message || "Generating document..."
      : randomThinking;

  // Steps where the dedicated AssistantLoadingState replaces the simple
  // "thinking" indicator. Covers component generation and flow building.
  //
  // ``generating_document`` is intentionally OUT — the manage_files path
  // shows only the simple thinking dots during the wait, then jumps
  // directly to the file card. A rich loading card that then morphs into
  // the file card looked like a glitch.
  const RICH_LOADING_STEPS = [
    "generating_component",
    "generating_flow",
    "extracting_code",
    "validating",
    "validation_failed",
    "retrying",
    "validated",
    "searching_components",
    "building_flow",
    "flow_built",
    "flow_build_failed",
  ];

  // Detect component code in streaming content (handles misclassified intent
  // when the LLM emits a component class without a generating_component step).
  const contentLooksLikeComponentCode =
    isStreaming &&
    message.content &&
    /```python[\s\S]*class\s+\w+.*Component/.test(message.content);

  // True when the rich loading state (component or flow build) should render
  // instead of the simple thinking indicator.
  const showsRichLoadingState =
    (message.progress && RICH_LOADING_STEPS.includes(message.progress.step)) ||
    contentLooksLikeComponentCode;

  // Show loading state during component generation or flow build.
  const isGeneratingCode = isStreaming && showsRichLoadingState;

  const renderContent = () => {
    // Show detailed loading state during component generation.
    // Keep showing it until validation animation completes.
    //
    // manage_files path: NO Continue gate. The card jumps straight to its
    // final state when the file is ready — the agent's text response gives
    // the user enough context, and a Continue button just adds friction for
    // a non-destructive action.
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

    // manage_files path: render one card per file the agent persisted.
    // No gate — non-destructive action, the user sees the agent's text
    // alongside the cards and can Open/Download directly.
    if (hasWrittenFiles && message.writtenFiles) {
      const cleanContent = message.content
        ?.replace(/```\w*\s*[\s\S]*?```/g, "")
        .replace(/\n{3,}/g, "\n\n")
        .trim();
      return (
        <div className="flex flex-col gap-3">
          {cleanContent && (
            <Markdown
              remarkPlugins={[remarkGfm]}
              className="prose prose-sm max-w-full text-muted-foreground dark:prose-invert prose-p:leading-relaxed prose-p:my-1"
            >
              {cleanContent}
            </Markdown>
          )}
          {message.writtenFiles.map((file) => (
            <AssistantFileCard
              key={`${file.action}-${file.path}-${file.receivedAt}`}
              file={file}
              onOpen={(f) => setOpenFilePath(f.path)}
            />
          ))}
        </div>
      );
    }

    // Show flow edit cards when agent proposed changes
    if (message.flowActions && message.flowActions.length > 0) {
      return (
        <div className="flex flex-col gap-3">
          {message.content && (
            <Markdown
              remarkPlugins={[remarkGfm]}
              className="prose prose-sm max-w-full text-muted-foreground dark:prose-invert prose-p:leading-relaxed prose-p:my-1"
            >
              {message.content}
            </Markdown>
          )}
          <FlowEditCarousel
            actions={message.flowActions}
            onUpdateAction={(actionId, status) =>
              onUpdateFlowAction?.(message.id, actionId, status)
            }
          />
        </div>
      );
    }

    // Gated flow proposal: agent built a new flow from scratch via set_flow.
    // Show the preview behind a Continue/Dismiss gate so the user can refuse
    // a destructive canvas replacement.
    if (message.flowProposalStatus && message.pendingFlowProposal) {
      const proposalPreview = {
        flow: message.pendingFlowProposal.flow,
        name: message.pendingFlowProposal.name ?? "",
        nodeCount: message.pendingFlowProposal.nodeCount,
        edgeCount: message.pendingFlowProposal.edgeCount,
        graph: "",
      };
      const cleanContent = message.content
        ?.replace(/```flow_json[\s\S]*?```/gi, "")
        .replace(/\n{3,}/g, "\n\n")
        .trim();
      return (
        <div className="flex flex-col gap-3">
          {cleanContent && (
            <Markdown
              remarkPlugins={[remarkGfm]}
              className="prose prose-sm max-w-full text-muted-foreground dark:prose-invert prose-p:leading-relaxed prose-p:my-1"
            >
              {cleanContent}
            </Markdown>
          )}
          <AssistantFlowPreview
            flowPreview={proposalPreview}
            status={message.flowProposalStatus}
            onApply={() => onApplyFlowProposal?.(message.id)}
            onDismiss={() => onDismissFlowProposal?.(message.id)}
          />
        </div>
      );
    }

    // Once applied, pendingFlowProposal is cleared and only flowProposalStatus
    // remains. Render the muted applied-state card from message.flowPreview
    // (legacy field carried for serialized sessions) if present.

    // Show flow preview when a flow was built (legacy path)
    if (message.flowPreview) {
      // Strip the flow_json code block from the visible content
      const cleanContent = message.content
        ?.replace(/```flow_json[\s\S]*?```/gi, "")
        .replace(/\n{3,}/g, "\n\n")
        .trim();
      return (
        <div className="flex flex-col gap-3">
          {cleanContent && (
            <Markdown
              remarkPlugins={[remarkGfm]}
              className="prose prose-sm max-w-full text-muted-foreground dark:prose-invert prose-p:leading-relaxed prose-p:my-1"
            >
              {cleanContent}
            </Markdown>
          )}
          <AssistantFlowPreview flowPreview={message.flowPreview} />
        </div>
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
      {openFilePath && (
        <FileContentModal
          path={openFilePath}
          content={
            message.writtenFiles?.find((f) => f.path === openFilePath)?.content
          }
          open={openFilePath !== null}
          onClose={() => setOpenFilePath(null)}
        />
      )}
    </div>
  );
}
