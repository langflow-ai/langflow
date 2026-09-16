import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import HumanInputCard, {
  type HumanInputDecision,
} from "@/components/core/chatComponents/HumanInputCard";
import { Button } from "@/components/ui/button";
import { toInteractiveContent } from "@/controllers/API/agui/human-input-card";
import {
  type EvalRun,
  isEvalRunActive,
  useCancelEvalRun,
} from "@/controllers/API/queries/folders/use-eval-suite";
import { useResumeWorkflow } from "@/controllers/API/queries/workflows/use-resume-workflow";

export function EvalRunProgress({
  projectId,
  run,
}: {
  projectId: string;
  run: EvalRun;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const cancel = useCancelEvalRun(projectId);
  const resume = useResumeWorkflow({ retry: false });
  const [error, setError] = useState("");
  const [stopping, setStopping] = useState(false);
  const pending = run.pending_approval;
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["evalRuns", projectId] });
  const stop = async () => {
    setError("");
    setStopping(true);
    try {
      await cancel.mutateAsync(run.id);
    } catch {
      setError(t("evaluations.cancelError"));
      setStopping(false);
    }
  };
  const decide = async (decision: HumanInputDecision) => {
    if (!pending) return;
    setError("");
    try {
      await resume.mutateAsync({
        jobId: pending.job_id,
        requestId: String(pending.request.request_id),
        decision,
      });
    } catch (cause) {
      const status = (cause as { response?: { status?: number } }).response
        ?.status;
      setError(
        t(
          status === 409
            ? "evaluations.staleApproval"
            : "evaluations.resumeError",
        ),
      );
      if (status !== 409) throw cause;
    } finally {
      void refresh();
    }
  };
  const active = isEvalRunActive(run);
  const current = run.result?.current ?? pending;
  const currentCase = run.result?.suite.cases.find(
    (item) => item.id === current?.case_id,
  );
  const cancelling = stopping || run.cancel_requested;
  return (
    <div className="space-y-3">
      {active && (
        <div className="flex items-center justify-between gap-4 rounded-md border bg-muted/30 p-4">
          <div className="space-y-1" role="status">
            <p className="text-sm font-medium">
              {t(
                cancelling
                  ? "evaluations.cancelling"
                  : `evaluations.status.${run.status}`,
              )}
            </p>
            <p className="text-sm text-muted-foreground">
              {t("evaluations.progress", {
                done: run.result?.cases.length ?? 0,
                total: run.result?.suite.cases.length ?? 0,
              })}
              {current &&
                ` · ${currentCase?.name ?? current.case_id} · ${t(`evaluations.phase.${current.phase}`)}`}
            </p>
            <p className="text-xs text-muted-foreground">
              {t("evaluations.backgroundHint")}
            </p>
          </div>
          <Button
            variant="outline"
            disabled={!!cancelling || cancel.isPending}
            onClick={() => void stop()}
          >
            {t("evaluations.cancel")}
          </Button>
        </div>
      )}
      {active && pending && (
        <HumanInputCard
          key={String(pending.request.request_id)}
          content={toInteractiveContent(pending.request, pending.job_id)}
          submitted={!!cancelling || resume.isPending}
          onSubmit={decide}
        />
      )}
      {run.error && (
        <p role="alert" className="text-sm text-destructive">
          {t(`evaluations.errors.${run.error}`, {
            defaultValue: t("evaluations.executionError"),
          })}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
