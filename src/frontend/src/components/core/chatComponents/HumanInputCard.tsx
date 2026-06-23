import { useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { queryClient } from "@/contexts";
import {
  getResumeContext,
  markHumanInputSubmitted,
} from "@/controllers/API/agui/human-input-card";
import { consumeBackgroundEvents } from "@/controllers/API/agui/run-flow-bridge";
import { useResumeWorkflow } from "@/controllers/API/queries/workflows/use-resume-workflow";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useHitlStore } from "@/stores/hitlStore";
import type { InteractiveContent } from "@/types/chat";
import { cn } from "@/utils/utils";
import ForwardedIconComponent from "../../common/genericIconComponent";

export interface HumanInputDecision {
  action_id: string;
  values: Record<string, string>;
}

const WAITING_FALLBACK_TEXT =
  "The flow has paused and is waiting for your decision before continuing.";

// Map an action to its Figma style: Approve is the filled primary, Reject is the
// red outline; everything else stays a neutral outline.
function decisionButtonClass(actionId: string): string {
  if (actionId === "approve") {
    return "border border-accent-indigo-foreground bg-accent-indigo-foreground text-white hover:bg-accent-indigo-foreground/90";
  }
  if (actionId === "reject") {
    return "border border-accent-red-foreground/40 bg-transparent text-accent-red-foreground hover:bg-accent-red-foreground/10";
  }
  return "border border-border bg-transparent text-foreground hover:bg-muted";
}

/**
 * Interactive human-in-the-loop card: a prompt, optional editable form fields, and
 * one button per decision. Mirrors the convergent HITL pattern (a paused turn the
 * user resolves inline) using Langflow's own components. Submit is single-use in the
 * UI (best-effort; the server is authoritative and returns 409 on a stale resume).
 */
export default function HumanInputCard({
  content,
  onSubmit,
  submitted = false,
}: {
  content: InteractiveContent;
  onSubmit?: (decision: HumanInputDecision) => void;
  submitted?: boolean;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [localChosen, setLocalChosen] = useState<string | null>(null);
  const fields = content.schema ?? content.fields ?? [];
  const { mutate: resume, isPending } = useResumeWorkflow();
  const setErrorData = useAlertStore((s) => s.setErrorData);
  // Derive from the persisted/cached content first so the choice survives re-renders
  // (the resume reattach replays the stream and re-renders the message list).
  const chosen = content.submitted_action ?? localChosen;
  const isSubmitted = submitted || chosen !== null;

  // Resume the suspended run and reattach to its durable event stream so the
  // continued run renders into the same chat session.
  const resumeRun = (decision: HumanInputDecision) => {
    const jobId = content.job_id;
    if (!jobId) {
      setErrorData({ title: "Cannot resume: missing job id" });
      setLocalChosen(null);
      return;
    }
    resume(
      { jobId, requestId: content.request_id, decision },
      {
        onSuccess: () => {
          const flowStore = useFlowStore.getState();
          flowStore.setAwaitingInput(false);
          // Resolve the canvas badge now — covers the reconnect path with no reattach.
          useHitlStore.getState().clear();
          // Resume synchronously drops this pause from the pending list and stamps submitted_action
          // on the card; refetch both so every surface re-derives as resolved (reattach won't).
          void queryClient.invalidateQueries({
            queryKey: ["useGetPendingWorkflows"],
          });
          void queryClient.invalidateQueries({
            queryKey: ["useGetMessagesQuery"],
          });
          const reattach = getResumeContext(content.request_id);
          if (reattach) {
            flowStore.setIsBuilding(true);
            void consumeBackgroundEvents(
              reattach.jobId,
              reattach.opts,
              undefined,
              {
                skipCardInjection: true,
              },
            );
          }
        },
        onError: (err: Error) => {
          // 409 means the run was already resumed (single-use) — keep the card
          // locked on the choice; only a genuine failure re-opens the buttons.
          const status = (err as { response?: { status?: number } })?.response
            ?.status;
          if (status === 409) return;
          setLocalChosen(null);
          setErrorData({ title: "Resume failed", list: [err.message] });
        },
      },
    );
  };

  const handleDecision = (actionId: string) => {
    if (isSubmitted || isPending) return;
    setLocalChosen(actionId);
    markHumanInputSubmitted(content.request_id, actionId);
    const decision = { action_id: actionId, values };
    if (onSubmit) onSubmit(decision);
    else resumeRun(decision);
  };

  return (
    <div
      data-testid="human-input-card"
      className="flex flex-col overflow-hidden rounded-xl border border-accent-indigo-foreground/40"
    >
      <div className="flex items-center gap-2 border-b border-accent-indigo-foreground/20 bg-accent-indigo-foreground/5 px-4 py-3 text-base font-semibold text-accent-indigo-foreground">
        <ForwardedIconComponent name="CirclePause" className="h-5 w-5" />
        <span>Waiting for input</span>
      </div>

      <div className="flex flex-col gap-3 px-4 py-3">
        <div className="prose prose-sm dark:prose-invert max-w-none text-sm text-muted-foreground">
          {content.prompt ? (
            <Markdown remarkPlugins={[remarkGfm]}>{content.prompt}</Markdown>
          ) : (
            <p>{WAITING_FALLBACK_TEXT}</p>
          )}
        </div>

        {fields.length > 0 && (
          <div className="flex flex-col gap-2">
            {fields.map((field) => (
              <label key={field.name} className="flex flex-col gap-1 text-xs">
                <span className="text-muted-foreground">
                  {field.name}
                  {field.required ? " *" : ""}
                </span>
                <Input
                  data-testid={`human-input-field-${field.name}`}
                  disabled={isSubmitted}
                  value={values[field.name] ?? ""}
                  onChange={(e) =>
                    setValues((prev) => ({
                      ...prev,
                      [field.name]: e.target.value,
                    }))
                  }
                />
              </label>
            ))}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          {content.options
            .filter((option) => chosen === null || option.action_id === chosen)
            .map((option) => (
              <Button
                key={option.action_id}
                data-testid={`human-input-decision-${option.action_id}`}
                unstyled
                disabled={isSubmitted || isPending}
                onClick={() => handleDecision(option.action_id)}
                className={cn(
                  "inline-flex items-center justify-center rounded-[10px] px-3 py-1.5 text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-70",
                  decisionButtonClass(option.action_id),
                )}
              >
                {chosen === option.action_id && (
                  <ForwardedIconComponent
                    name="Check"
                    className="mr-1 h-3.5 w-3.5"
                  />
                )}
                {option.label || option.action_id}
              </Button>
            ))}
        </div>
      </div>
    </div>
  );
}
