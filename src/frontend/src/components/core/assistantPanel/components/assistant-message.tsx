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
import { AssistantModelNotice } from "./assistant-model-notice";
import { AssistantRevertAction } from "./assistant-revert-action";
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
  onRevertFlowProposal?: (messageId: string) => void;
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
  /**
   * v1 scope: the Revert action renders ONLY on the latest assistant
   * message with a restore point — older ones are hidden to avoid
   * mid-chain restore confusion.
   */
  isLatestRestorePoint?: boolean;
  /** Marks the message as reverted after a successful restore. */
  onReverted?: (messageId: string) => void;
}

// Steps where AssistantLoadingState replaces the simple thinking dots.
// generating_document is OUT: dots → file card directly, no morphing glitch.
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
  onRevertFlowProposal,
  onDismissFlowProposal,
  onApprovePlan,
  onDismissPlan,
  onResetPlan,
  onRetry,
  skipApprovalGate = false,
  onAcknowledgeValidation,
  isLatestRestorePoint = false,
  onReverted,
}: AssistantMessageItemProps) {
  const { t } = useTranslation();
  const isUser = message.role === "user";
  const isStreaming = message.status === "streaming";

  // Modal state for "Open" on a file card. Single-modal-at-a-time per message
  // so the user always has clear focus on which file they're inspecting.
  const [openFilePath, setOpenFilePath] = useState<string | null>(null);

  // Randomized once per message; manage_files overrides with the static
  // "Generating document..." so the dots match the input placeholder.
  const randomThinking = useMemo(() => getRandomThinkingMessage(), []);

  // Memoized misclassified-intent detector (regex per token was hot); must stay
  // above the `message.hidden` early return to keep the hook count stable.
  const contentLooksLikeComponentCode = useMemo(
    () =>
      isStreaming &&
      !!message.content &&
      /```python[\s\S]*class\s+\w+.*Component/.test(message.content),
    [isStreaming, message.content],
  );

  // Skip-all hides the propose_plan preamble entirely; guard AFTER hooks
  // so the hook count stays stable across renders (Rules of Hooks).
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

  // Suppress the "Working on the flow…" build spinner while a plan is still
  // pending — the agent is only planning, no build is happening yet.
  const planPending =
    message.planProposalStatus === "pending" && !!message.pendingPlanProposal;
  const inProgressTask = planPending ? undefined : message.inProgressTask;

  // One build indicator only: when the "Working on the flow…" row shows, drop
  // the redundant rich "Building the flow…" loader so exactly one is visible.
  const isGeneratingCode =
    isStreaming && Boolean(showsRichLoadingState) && !inProgressTask;

  // Simple thinking: streaming with no content, rich state, or build row yet.
  const isSimpleThinking =
    isStreaming && !isGeneratingCode && !message.content && !inProgressTask;

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
            {!isUser &&
              message.status === "complete" &&
              message.notices &&
              message.notices.length > 0 && (
                <AssistantModelNotice notices={message.notices} />
              )}
          </div>
          {/* While a plan awaits the user the agent is only planning, so a
              build spinner must not flash before/beside the plan card. */}
          {!isUser &&
            ((message.buildTasks && message.buildTasks.length > 0) ||
              inProgressTask) && (
              <AssistantBuildTasks
                tasks={message.buildTasks ?? []}
                inProgressTask={inProgressTask}
                hasError={message.status === "error"}
              />
            )}
          <div className="mt-3 overflow-hidden">
            <AssistantMessageBody
              message={message}
              isGeneratingCode={isGeneratingCode}
              skipApprovalGate={skipApprovalGate}
              onApprove={onApprove}
              onUpdateFlowAction={onUpdateFlowAction}
              onApplyFlowProposal={onApplyFlowProposal}
              onRevertFlowProposal={onRevertFlowProposal}
              onDismissFlowProposal={onDismissFlowProposal}
              onApprovePlan={onApprovePlan}
              onDismissPlan={onDismissPlan}
              onResetPlan={onResetPlan}
              onRetry={onRetry}
              onAcknowledgeValidation={onAcknowledgeValidation}
              onOpenFile={(path) => setOpenFilePath(path)}
            />
          </div>
          {!isUser &&
            message.status === "complete" &&
            message.restoreVersionId &&
            isLatestRestorePoint &&
            // Gated proposals own their revert via the card's Revert button;
            // suppress the version-based footer so there is a single affordance.
            !message.pendingFlowProposal && (
              <AssistantRevertAction
                restoreVersionId={message.restoreVersionId}
                reverted={Boolean(message.reverted)}
                onReverted={() => onReverted?.(message.id)}
              />
            )}
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
