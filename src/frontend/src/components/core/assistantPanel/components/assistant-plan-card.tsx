import { ArrowRight, ClipboardList, RotateCcw, X } from "lucide-react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/utils/utils";
import type { PlanProposalStatus } from "../assistant-panel.types";
import {
  GHOST_PRIMARY_BUTTON,
  GHOST_SECONDARY_BUTTON,
} from "../helpers/button-styles";

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
        "max-w-[80%] py-1 transition-opacity",
        isRefining && "opacity-70",
      )}
    >
      <div className="mb-2 flex items-center gap-2">
        <ClipboardList
          className={cn(
            "h-4 w-4",
            isRefining ? "text-muted-foreground" : "text-foreground/80",
          )}
        />
        <span
          className={cn(
            "text-sm font-semibold",
            isRefining ? "text-muted-foreground" : "text-foreground",
          )}
        >
          {isRefining ? "Refining plan" : "Proposed plan"}
        </span>
        {isRefining && (
          <span className="text-xs text-muted-foreground/70">
            Send your changes…
          </span>
        )}
      </div>

      <div className="custom-scroll mb-3 max-h-[280px] overflow-y-auto rounded-md bg-muted/30 px-3 py-2">
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

      <div className="flex items-center gap-1">{renderActions()}</div>
    </div>
  );

  function renderActions() {
    if (status === "refining") {
      return (
        <>
          <button
            type="button"
            data-testid="assistant-plan-continue-button"
            className={GHOST_PRIMARY_BUTTON}
            onClick={() => onApprove?.()}
          >
            <span>Continue</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            data-testid="assistant-plan-reset-button"
            className={GHOST_SECONDARY_BUTTON}
            onClick={() => onReset?.()}
          >
            <RotateCcw className="h-3.5 w-3.5" />
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
            className={GHOST_PRIMARY_BUTTON}
            onClick={() => onApprove?.()}
          >
            <span>Continue</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            data-testid="assistant-plan-dismiss-button"
            className={GHOST_SECONDARY_BUTTON}
            onClick={() => onDismiss?.()}
          >
            <X className="h-3.5 w-3.5" />
            <span>Dismiss</span>
          </button>
        </>
      );
    }
    if (status === "approved") {
      return (
        <div className="flex h-7 items-center gap-1.5 px-2 text-sm font-medium text-accent-emerald-foreground">
          <ArrowRight className="h-3.5 w-3.5" />
          <span>Plan approved</span>
        </div>
      );
    }
    return (
      <div className="flex h-7 items-center gap-1.5 px-2 text-sm font-medium text-muted-foreground line-through">
        <span>Dismissed</span>
      </div>
    );
  }
}
