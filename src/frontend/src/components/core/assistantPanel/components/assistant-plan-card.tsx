import { ArrowRight, ClipboardList, X } from "lucide-react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { PlanProposalStatus } from "../assistant-panel.types";

interface AssistantPlanCardProps {
  /** Raw markdown body of the plan as emitted by the agent's propose_plan tool. */
  markdown: string;
  /** Pending = show Continue/Dismiss. Approved/dismissed = muted summary. */
  status: PlanProposalStatus;
  /** Fires when the user clicks Continue. */
  onApprove?: () => void;
  /** Fires when the user clicks Dismiss. */
  onDismiss?: () => void;
}

/**
 * Planning gate that runs BEFORE the agent calls search/describe/build_flow
 * in BUILD mode. The agent's propose_plan tool emits a markdown summary; this
 * card renders it with Continue/Dismiss buttons. Continue unblocks the agent
 * (it sends a fresh user turn with an approval signal). Dismiss leaves the
 * chat open so the user can type refinement feedback.
 */
export function AssistantPlanCard({
  markdown,
  status,
  onApprove,
  onDismiss,
}: AssistantPlanCardProps) {
  return (
    <div className="max-w-[80%] rounded-lg border border-border bg-muted/30 p-4">
      <div className="mb-3 flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-[#8B5CF6]">
          <ClipboardList className="h-4 w-4 text-white" />
        </div>
        <span className="text-sm font-semibold text-foreground">
          Proposed plan
        </span>
      </div>

      <div className="mb-4 max-h-[240px] overflow-y-auto rounded-md border border-border bg-background p-3">
        <Markdown
          remarkPlugins={[remarkGfm]}
          className="prose prose-sm max-w-full text-foreground dark:prose-invert prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-headings:my-2"
        >
          {markdown}
        </Markdown>
      </div>

      <div className="flex items-center gap-2">{renderActions()}</div>
    </div>
  );

  function renderActions() {
    if (status === "pending") {
      return (
        <>
          <button
            type="button"
            data-testid="assistant-plan-continue-button"
            className="flex h-8 items-center gap-1.5 rounded-[10px] bg-accent-emerald-foreground/10 px-3 text-sm font-medium text-accent-emerald-foreground transition-colors hover:bg-accent-emerald-foreground/20"
            onClick={() => onApprove?.()}
          >
            <span>Continue</span>
            <ArrowRight className="h-4 w-4" />
          </button>
          <button
            type="button"
            data-testid="assistant-plan-dismiss-button"
            className="flex h-8 items-center gap-1.5 rounded-[10px] bg-zinc-700 px-3 text-sm font-medium text-white transition-colors hover:bg-zinc-600"
            onClick={() => onDismiss?.()}
          >
            <X className="h-4 w-4" />
            <span>Dismiss</span>
          </button>
        </>
      );
    }
    if (status === "approved") {
      return (
        <div className="flex h-8 items-center gap-1.5 text-sm font-medium text-accent-emerald-foreground">
          <ArrowRight className="h-4 w-4" />
          <span>Plan approved</span>
        </div>
      );
    }
    return (
      <div className="flex h-8 items-center gap-1.5 text-sm font-medium text-muted-foreground line-through">
        <span>Dismissed</span>
      </div>
    );
  }
}
