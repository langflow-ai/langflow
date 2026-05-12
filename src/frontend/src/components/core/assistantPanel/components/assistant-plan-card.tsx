import { ArrowRight, ClipboardList, RotateCcw, X } from "lucide-react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/utils/utils";
import type { PlanProposalStatus } from "../assistant-panel.types";

interface AssistantPlanCardProps {
  /** Raw markdown body of the plan as emitted by the agent's propose_plan tool. */
  markdown: string;
  /** Drives which actions render. */
  status: PlanProposalStatus;
  /** Fires when the user clicks Continue (pending or refining state). */
  onApprove?: () => void;
  /** Fires when the user clicks Dismiss (pending state only). */
  onDismiss?: () => void;
  /** Fires when the user clicks Reset (refining state only). */
  onReset?: () => void;
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
  onReset,
}: AssistantPlanCardProps) {
  const isRefining = status === "refining";
  return (
    <div
      className={cn(
        "max-w-[80%] rounded-lg border p-4 transition-colors",
        isRefining
          ? "border-dashed border-muted-foreground/40 bg-muted/20"
          : "border-border bg-muted/30",
      )}
    >
      <div className="mb-3 flex items-center gap-3">
        <div
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-[10px]",
            isRefining ? "bg-muted-foreground/20" : "bg-[#8B5CF6]",
          )}
        >
          <ClipboardList
            className={cn(
              "h-4 w-4",
              isRefining ? "text-muted-foreground" : "text-white",
            )}
          />
        </div>
        <span
          className={cn(
            "text-sm font-semibold",
            isRefining ? "text-muted-foreground" : "text-foreground",
          )}
        >
          {isRefining ? "Refining plan" : "Proposed plan"}
        </span>
        {isRefining && (
          <span className="text-xs font-medium text-muted-foreground/80">
            Send your changes…
          </span>
        )}
      </div>

      <div className="mb-4 max-h-[240px] overflow-y-auto rounded-md border border-border bg-background p-3">
        <Markdown
          remarkPlugins={[remarkGfm]}
          className={cn(
            // Match the chat's body markdown sizing exactly so the plan
            // card doesn't visually outshout the surrounding messages.
            "prose prose-sm max-w-full text-muted-foreground dark:prose-invert",
            "prose-p:leading-relaxed prose-p:my-1",
            "prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5",
            // Headings: keep them bold but at body size (or one notch
            // up for h1/h2) — Tailwind Typography's default scales them
            // ~1.5x which dwarfs the surrounding chat text.
            "prose-headings:my-2 prose-headings:font-semibold prose-headings:text-foreground",
            "prose-h1:text-sm prose-h2:text-sm prose-h3:text-sm prose-h4:text-sm",
            "prose-strong:text-foreground",
          )}
        >
          {markdown}
        </Markdown>
      </div>

      <div className="flex items-center gap-2">{renderActions()}</div>
    </div>
  );

  function renderActions() {
    if (status === "refining") {
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
            data-testid="assistant-plan-reset-button"
            className="flex h-8 items-center gap-1.5 rounded-[10px] bg-zinc-700 px-3 text-sm font-medium text-white transition-colors hover:bg-zinc-600"
            onClick={() => onReset?.()}
          >
            <RotateCcw className="h-4 w-4" />
            <span>Reset</span>
          </button>
        </>
      );
    }
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
