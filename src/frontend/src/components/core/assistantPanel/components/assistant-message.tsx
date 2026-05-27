import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import langflowAssistantIcon from "@/assets/langflow_assistant.svg";
import MessageMetadata from "@/components/common/messageMetadataComponent";
import { CustomProfileIcon } from "@/customization/components/custom-profile-icon";
import { cn } from "@/utils/utils";
import type { AssistantMessage } from "../assistant-panel.types";
import { getRandomThinkingMessage } from "../helpers/messages";
import { AssistantBuildTasks } from "./assistant-build-tasks";
import { AssistantMessageBody } from "./assistant-message-body";
import { FileContentModal } from "./file-content-modal";

interface AssistantMessageItemProps {
  message: AssistantMessage;
  onApprove?: (messageId: string) => void;
  onUpdateFlowAction?: (
    messageId: string,
    actionId: string,
    status: "applied" | "dismissed",
  ) => void;
  onApplyFlowProposal?: (messageId: string, mode?: "replace" | "add") => void;
  onDismissFlowProposal?: (messageId: string) => void;
  onApprovePlan?: (messageId: string) => void;
  onDismissPlan?: (messageId: string) => void;
  /** Fires when the user clicks Reset on a refining plan card. */
  onResetPlan?: (messageId: string) => void;
  onRetry?: (messageId: string) => void;
  /**
   * When true, the message renders past the validation/document Continue
   * gate immediately — no manual user click. Driven by the hook's
   * persistent skip-all preference.
   */
  skipApprovalGate?: boolean;
  /**
   * Persists the user's acknowledgement of the validation gate (Continue
   * click or 30s auto-dismiss) onto the message itself so panel
   * close/reopen doesn't bring the gate back.
   */
  onAcknowledgeValidation?: (messageId: string) => void;
}

// Steps where the dedicated AssistantLoadingState replaces the simple
// "thinking" indicator. Covers component generation and flow building.
//
// ``generating_document`` is intentionally OUT — the manage_files path
// shows only the simple thinking dots during the wait, then jumps
// directly to the file card. A rich loading card that then morphs into
// the file card looked like a glitch.
const RICH_LOADING_STEPS = [
  "generating_component",
  "generating_plan",
  "generating_flow",
  "generating_document",
  "orchestrating",
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
  onApprovePlan,
  onDismissPlan,
  onResetPlan,
  onRetry,
  skipApprovalGate = false,
  onAcknowledgeValidation,
}: AssistantMessageItemProps) {
  const { t } = useTranslation();
  const isUser = message.role === "user";
  const isStreaming = message.status === "streaming";

  // Modal state for "Open" on a file card. Single-modal-at-a-time per message
  // so the user always has clear focus on which file they're inspecting.
  const [openFilePath, setOpenFilePath] = useState<string | null>(null);

  // Generate randomized messages once per message. For manage_files we
  // override the random label with the static "Generating document..." so
  // the thinking dots match the input placeholder (no rotating noise).
  const randomThinking = useMemo(() => getRandomThinkingMessage(), []);

  // Detect component code in streaming content (handles misclassified intent
  // when the LLM emits a component class without a generating_component step).
  // R5: regex was running on every render (every streaming chunk) — memoize so
  // the test only runs when the inputs that drive it actually change. Hook
  // MUST live above the `if (message.hidden) return null` early return below
  // to keep the hook count stable (Rules of Hooks).
  const contentLooksLikeComponentCode = useMemo(
    () =>
      isStreaming &&
      !!message.content &&
      /```python[\s\S]*class\s+\w+.*Component/.test(message.content),
    [isStreaming, message.content],
  );

  // Hidden messages bypass rendering entirely. Used by skip-all to drop
  // the propose_plan turn's preamble so the chat reads as "user prompt →
  // built flow" with nothing in between. Guard AFTER hooks so the hook
  // count stays stable across renders (Rules of Hooks).
  if (message.hidden) {
    return null;
  }
  const thinkingMessage =
    message.progress?.step === "generating_document"
      ? message.progress.message || "Generating document..."
      : randomThinking;

  // True when the rich loading state (component or flow build) should render
  // instead of the simple thinking indicator.
  const showsRichLoadingState =
    (message.progress && RICH_LOADING_STEPS.includes(message.progress.step)) ||
    contentLooksLikeComponentCode;

  // Show loading state during component generation or flow build.
  const isGeneratingCode = isStreaming && Boolean(showsRichLoadingState);

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
    <div
      className="mb-6"
      data-testid={
        isUser ? "assistant-message-user" : "assistant-message-assistant"
      }
    >
      <div className="flex items-start gap-3">
        {isUser ? (
          <CustomProfileIcon className="h-7 w-7 shrink-0 rounded-full" />
        ) : (
          <div className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-lg">
            <img
              src={langflowAssistantIcon}
              alt={t("assistant.title")}
              className="h-full w-full object-cover"
            />
          </div>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "text-[13px] font-semibold leading-4",
                isUser ? "text-foreground" : "text-accent-pink-foreground",
              )}
            >
              {isUser ? t("assistant.user") : t("assistant.title")}
            </span>
            {!isUser && message.status === "complete" && (
              <MessageMetadata
                usage={message.usage}
                duration={message.duration}
                subtle
              />
            )}
          </div>
          {!isUser && message.buildTasks && message.buildTasks.length > 0 && (
            <AssistantBuildTasks tasks={message.buildTasks} />
          )}
          <div className="mt-3 overflow-hidden">
            <AssistantMessageBody
              message={message}
              isGeneratingCode={isGeneratingCode}
              skipApprovalGate={skipApprovalGate}
              onApprove={onApprove}
              onUpdateFlowAction={onUpdateFlowAction}
              onApplyFlowProposal={onApplyFlowProposal}
              onDismissFlowProposal={onDismissFlowProposal}
              onApprovePlan={onApprovePlan}
              onDismissPlan={onDismissPlan}
              onResetPlan={onResetPlan}
              onRetry={onRetry}
              onAcknowledgeValidation={onAcknowledgeValidation}
              onOpenFile={(path) => setOpenFilePath(path)}
            />
          </div>
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
