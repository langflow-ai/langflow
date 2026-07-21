import { useState } from "react";
import { useTranslation } from "react-i18next";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { queryClient } from "@/contexts";
import {
  getResumeContext,
  markHumanInputSubmitted,
} from "@/controllers/API/agui/human-input-card";
import { consumeBackgroundEvents } from "@/controllers/API/agui/run-flow-bridge";
import type { PendingHumanRequest } from "@/controllers/API/queries/workflows/use-get-pending-workflows";
import { useResumeWorkflow } from "@/controllers/API/queries/workflows/use-resume-workflow";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useHitlStore } from "@/stores/hitlStore";

/**
 * Bottom bar for a paused (awaiting-human) trace: mirrors the chat/canvas HITL card,
 * resolving the SUSPENDED run via the same resume endpoint and showing a resuming state.
 */
export function TraceHitlBar({
  pending,
  onResolved,
  onDecision,
}: {
  pending: PendingHumanRequest;
  onResolved?: () => void;
  onDecision?: (actionId: string) => void;
}): JSX.Element {
  const { t } = useTranslation();
  const { mutate: resume, isPending } = useResumeWorkflow();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [resuming, setResuming] = useState(false);

  const options = pending.options.length
    ? pending.options
    : pending.allowed_decisions.map((id) => ({
        action_id: id,
        label: undefined,
      }));

  // Drive every surface (canvas badge, playground, node statuses) live off the resumed
  // run's event stream, mirroring the chat card — so nothing requires a hard refresh.
  const reattachAndResolve = () => {
    useHitlStore.getState().clear();
    const flowStore = useFlowStore.getState();
    flowStore.setAwaitingInput(false);
    const reattach = getResumeContext(pending.request_id) ?? {
      jobId: pending.job_id,
      opts: {
        flowId: pending.flow_id,
        threadId: pending.session_id ?? undefined,
      },
    };
    flowStore.setIsBuilding(true);
    void consumeBackgroundEvents(
      reattach.jobId,
      { ...reattach.opts, silent: true },
      undefined,
      { skipCardInjection: true },
    );
    queryClient.invalidateQueries({ queryKey: ["useGetTracesQuery"] });
    queryClient.invalidateQueries({ queryKey: ["useGetPendingWorkflows"] });
    queryClient.invalidateQueries({ queryKey: ["useGetTraceQuery"] });
    onResolved?.();
  };

  const decide = (actionId: string) => {
    if (isPending || resuming) return;
    setResuming(true);
    onDecision?.(actionId);
    markHumanInputSubmitted(pending.request_id, actionId);
    resume(
      {
        jobId: pending.job_id,
        requestId: pending.request_id,
        decision: { action_id: actionId, values: {} },
      },
      {
        onSuccess: reattachAndResolve,
        onError: (err: Error) => {
          const status = (err as { response?: { status?: number } })?.response
            ?.status;
          // 409 = already resumed (single-use); still reconcile the UI to the final state.
          if (status === 409) {
            reattachAndResolve();
            return;
          }
          setResuming(false);
          setErrorData({
            title: t("humanInput.resumeFailed"),
            list: [err.message],
          });
        },
      },
    );
  };

  const isReject = (id: string) => id.toLowerCase().includes("reject");

  return (
    <div className="flex items-center justify-between gap-3 border-t border-border bg-muted/40 px-4 py-3">
      <div className="flex min-w-0 items-center gap-2">
        <IconComponent
          name="Pause"
          className="h-4 w-4 shrink-0 text-accent-indigo-foreground"
        />
        <span className="text-sm font-medium text-primary">
          {t("trace.hitlTitle")}
        </span>
        <span className="truncate text-sm text-muted-foreground">
          {t("trace.awaitingDecision")}
        </span>
      </div>

      {resuming ? (
        <span className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="animate-pulse tracking-widest">•••</span>
          {t("trace.resumingFlow")}
        </span>
      ) : (
        <div className="flex shrink-0 items-center gap-2">
          {options.map((option) => (
            <Button
              key={option.action_id}
              size="sm"
              variant={isReject(option.action_id) ? "destructive" : "default"}
              disabled={isPending}
              data-testid={`trace-hitl-${option.action_id}`}
              onClick={() => decide(option.action_id)}
            >
              {option.label ?? option.action_id}
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}
