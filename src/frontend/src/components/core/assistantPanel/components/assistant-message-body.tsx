/**
 * Body of an assistant chat message — the part that switches between the
 * loading state, validated component result, file cards, plan card, flow
 * proposal card, and plain markdown response. Owns the validation-gate
 * acknowledgement state (Continue click / 30s timeout) so the parent
 * `AssistantMessageItem` stays focused on avatar + header layout.
 *
 * Why split from `AssistantMessageItem`: that file was approaching the
 * 500-line hard limit, and the rendering decision tree here grows whenever
 * the assistant gains a new response type. Keeping it separate gives that
 * tree room to evolve without dragging the layout shell with it.
 */

import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SimplifiedCodeTabComponent from "@/components/core/codeTabsComponent";
import { extractLanguage, isCodeBlock } from "@/utils/codeBlockUtils";
import type { AssistantMessage } from "../assistant-panel.types";
import { ChatMarkdown } from "../helpers/chat-markdown";
import { AssistantComponentResult } from "./assistant-component-result";
import { AssistantErrorDetails } from "./assistant-error-details";
import { AssistantFileCard } from "./assistant-file-card";
import { FlowEditCarousel } from "./assistant-flow-edit-card";
import { AssistantFlowPreview } from "./assistant-flow-preview";
import { AssistantLoadingState } from "./assistant-loading-state";
import { AssistantPlanCard } from "./assistant-plan-card";
import { AssistantValidationFailed } from "./assistant-validation-failed";

// Auto-dismiss the validation gate after this long in a terminal state, so the
// loading card never gets stuck if the user walks away without clicking Continue.
const VALIDATION_GATE_AUTO_DISMISS_MS = 30000;

export interface AssistantMessageBodyProps {
  message: AssistantMessage;
  /** True when streaming AND in a rich loading step (component/flow build). */
  isGeneratingCode: boolean;
  /** Pre-acknowledges the validation gate without a manual user click. */
  skipApprovalGate?: boolean;
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
  onResetPlan?: (messageId: string) => void;
  onRetry?: (messageId: string) => void;
  /** Persist the validation-gate acknowledgement onto the message itself. */
  onAcknowledgeValidation?: (messageId: string) => void;
  /** Callback when the user clicks Open on a written file card. */
  onOpenFile?: (path: string) => void;
}

export function AssistantMessageBody({
  message,
  isGeneratingCode,
  skipApprovalGate = false,
  onApprove,
  onUpdateFlowAction,
  onApplyFlowProposal,
  onRevertFlowProposal,
  onDismissFlowProposal,
  onApprovePlan,
  onDismissPlan,
  onResetPlan,
  onRetry,
  onAcknowledgeValidation,
  onOpenFile,
}: AssistantMessageBodyProps) {
  const isStreaming = message.status === "streaming";
  const hasValidatedResult =
    message.result?.validated && message.result?.componentCode;
  const hasValidationError =
    message.result?.validated === false && message.result?.validationError;
  const hasWrittenFiles = (message.writtenFiles?.length ?? 0) > 0;

  // skip-all pre-sets the gate to "complete"; validationAcknowledged is the
  // persisted twin so the gate doesn't reappear on remount (panel close+reopen).
  const [validationAnimationComplete, setValidationAnimationComplete] =
    useState(() => skipApprovalGate || Boolean(message.validationAcknowledged));

  // Persist the acknowledgement onto the message itself. Fires once when
  // the local state transitions to true (Continue click OR 30s timeout).
  useEffect(() => {
    if (validationAnimationComplete && !message.validationAcknowledged) {
      onAcknowledgeValidation?.(message.id);
    }
  }, [
    validationAnimationComplete,
    message.id,
    message.validationAcknowledged,
    onAcknowledgeValidation,
  ]);

  // Timeout fallback: if message is complete but user hasn't clicked
  // Continue, force-dismiss after ${VALIDATION_GATE_AUTO_DISMISS_MS}ms.
  useEffect(() => {
    if (
      message.status === "complete" &&
      (hasValidatedResult || hasValidationError) &&
      !validationAnimationComplete
    ) {
      const timer = setTimeout(() => {
        setValidationAnimationComplete(true);
      }, VALIDATION_GATE_AUTO_DISMISS_MS);
      return () => clearTimeout(timer);
    }
  }, [
    message.status,
    hasValidatedResult,
    hasValidationError,
    validationAnimationComplete,
  ]);

  // Detailed loading state during component generation, until the validation
  // animation completes. manage_files skips the gate — non-destructive action.
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

  if (message.status === "error" && message.error) {
    return (
      <div className="flex flex-col gap-1">
        <p className="text-sm font-normal text-destructive">{message.error}</p>
        {message.errorDetail && (
          <AssistantErrorDetails detail={message.errorDetail} />
        )}
      </div>
    );
  }

  if (message.status === "cancelled") {
    return (
      <span className="text-sm text-muted-foreground/60 italic">Cancelled</span>
    );
  }

  // Show validation failure after all retries (only after the animation
  // completes, or if no progress event ever arrived).
  const canShowResult = validationAnimationComplete || !message.progress;
  if (hasValidationError && message.result && canShowResult) {
    return (
      <AssistantValidationFailed
        result={message.result}
        onRetry={onRetry ? () => onRetry(message.id) : undefined}
      />
    );
  }

  // Successful component result (only after validation animation completes,
  // or if no animation was needed in the first place).
  if (hasValidatedResult && message.result && canShowResult) {
    return (
      <AssistantComponentResult
        result={message.result}
        onApprove={() => onApprove?.(message.id)}
      />
    );
  }

  // manage_files: render one card per persisted file. No gate — non-
  // destructive action; the user can Open/Download directly.
  if (hasWrittenFiles && message.writtenFiles) {
    const cleanContent = message.content
      ?.replace(/```\w*\s*[\s\S]*?```/g, "")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
    return (
      <div className="flex flex-col gap-3">
        {cleanContent && <ChatMarkdown>{cleanContent}</ChatMarkdown>}
        {message.writtenFiles.map((file) => (
          <AssistantFileCard
            key={`${file.action}-${file.path}-${file.receivedAt}`}
            file={file}
            onOpen={(f) => onOpenFile?.(f.path)}
          />
        ))}
      </div>
    );
  }

  if (message.flowActions && message.flowActions.length > 0) {
    return (
      <div className="flex flex-col gap-3">
        {message.content && <ChatMarkdown>{message.content}</ChatMarkdown>}
        <FlowEditCarousel
          actions={message.flowActions}
          onUpdateAction={(actionId, status) =>
            onUpdateFlowAction?.(message.id, actionId, status)
          }
        />
      </div>
    );
  }

  // BUILD-mode planning gate: propose_plan markdown behind Continue (resume
  // via a new user turn) / Dismiss (user types refinement, agent replans).
  if (message.planProposalStatus && message.pendingPlanProposal) {
    return (
      <div className="flex flex-col gap-3">
        {message.content && <ChatMarkdown>{message.content}</ChatMarkdown>}
        <AssistantPlanCard
          markdown={message.pendingPlanProposal.markdown}
          status={message.planProposalStatus}
          onApprove={() => onApprovePlan?.(message.id)}
          onDismiss={() => onDismissPlan?.(message.id)}
          onReset={() => onResetPlan?.(message.id)}
        />
      </div>
    );
  }

  // Gated flow proposal: a from-scratch set_flow previews behind Continue/
  // Dismiss so the user can refuse a destructive canvas replacement.
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
        {cleanContent && <ChatMarkdown>{cleanContent}</ChatMarkdown>}
        <AssistantFlowPreview
          flowPreview={proposalPreview}
          status={message.flowProposalStatus}
          onApply={(mode) => onApplyFlowProposal?.(message.id, mode)}
          onRevert={() => onRevertFlowProposal?.(message.id)}
          canRevert={Boolean(message.flowProposalSnapshot)}
          onDismiss={() => onDismissFlowProposal?.(message.id)}
        />
      </div>
    );
  }

  // Once applied, only flowProposalStatus remains — render the muted applied-
  // state card from message.flowPreview (legacy field for serialized sessions).
  if (message.flowPreview) {
    const cleanContent = message.content
      ?.replace(/```flow_json[\s\S]*?```/gi, "")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
    return (
      <div className="flex flex-col gap-3">
        {cleanContent && <ChatMarkdown>{cleanContent}</ChatMarkdown>}
        <AssistantFlowPreview flowPreview={message.flowPreview} />
      </div>
    );
  }

  // Default text content with rich markdown support (anchor + code blocks).
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
                language={extractLanguage(className)}
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
}
