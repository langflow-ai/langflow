import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useParams, useSearchParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { TERMINAL_RUN_STATUSES } from "@/controllers/API/queries/evals/types";
import {
  exportUrl,
  useCancelEvaluationRun,
  useGetEvaluation,
  useGetEvaluationRun,
  useGetEvaluationRuns,
} from "@/controllers/API/queries/evals/use-evaluations";
import { useDocumentTitle } from "@/hooks/use-document-title";
import ConfirmRunDialog from "@/modals/evaluateFlowModal/ConfirmRunDialog";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";
import BackLink from "./components/BackLink";
import EvalsPageShell from "./components/EvalsPageShell";
import { EvalsEmptyState } from "./components/EvalsStates";
import RunResults from "./components/RunResults";
import RunsTable, { versionTag } from "./components/RunsTable";
import { useRerun } from "./hooks/use-rerun";
import { downloadCsv } from "./utils/download-csv";

export default function EvaluationDetailPage() {
  const { t } = useTranslation();
  const { evaluationId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const onError = (title: string) => (error: unknown) =>
    setErrorData({ title, list: extractApiErrorMessages(error) });

  const { data: evaluation, isError: evaluationFailed } = useGetEvaluation({
    evaluationId,
  });
  const { data: runsPage, refetch: refetchRuns } = useGetEvaluationRuns({
    evaluationId,
    poll: true,
  });
  const runs = runsPage?.items ?? [];
  const anyActive = runs.some((run) => !TERMINAL_RUN_STATUSES.has(run.status));
  const selectedRunId = searchParams.get("run") ?? runs[0]?.id ?? null;
  const { data: selectedRun } = useGetEvaluationRun({
    runId: selectedRunId ?? "",
  });
  useDocumentTitle(evaluation?.name ?? t("evals.evaluations.title"));

  // Only the selected run polls fast; the list row follows its progress instead of polling alongside.
  const progress = selectedRun
    ? {
        id: selectedRun.id,
        step: `${selectedRun.status}:${selectedRun.completed_items}`,
      }
    : null;
  const lastProgress = useRef(progress);
  useEffect(() => {
    const previous = lastProgress.current;
    lastProgress.current = progress;
    if (
      previous &&
      progress &&
      previous.id === progress.id &&
      previous.step !== progress.step
    ) {
      void refetchRuns();
    }
  }, [progress?.id, progress?.step, refetchRuns]);

  const selectRun = (runId: string) => setSearchParams({ run: runId });
  const rerun = useRerun(evaluation, selectRun);
  const cancelRun = useCancelEvaluationRun(
    { runId: selectedRun?.id ?? "", evaluationId },
    { onError: onError(t("evals.runs.cancelError")) },
  );
  const selectedActive = Boolean(
    selectedRun && !TERMINAL_RUN_STATUSES.has(selectedRun.status),
  );
  const rerunBusy = rerun.estimating || rerun.starting;

  const handleExport = () => {
    if (!selectedRun) return;
    downloadCsv(exportUrl("run", selectedRun.id), "evaluation-run.csv").catch(
      onError(t("evals.exportError")),
    );
  };

  const back = (
    <BackLink to="/assets/evaluations" label={t("evals.evaluations.back")} />
  );
  if (evaluationFailed) {
    return (
      <EvalsPageShell
        title={t("evals.evaluations.notFoundTitle")}
        titleTestId="evaluation-detail-title"
        back={back}
      >
        <EvalsEmptyState
          icon="CircleAlert"
          title={t("evals.evaluations.notFoundTitle")}
          description={t("evals.evaluations.notFoundBody")}
          testId="evaluation-not-found"
        />
      </EvalsPageShell>
    );
  }

  return (
    <EvalsPageShell
      title={evaluation?.name ?? ""}
      titleTestId="evaluation-detail-title"
      back={back}
      actions={
        <>
          {selectedRun && (
            <Button variant="outline" onClick={handleExport}>
              <ForwardedIconComponent name="Download" className="h-4 w-4" />
              {t("evals.export")}
            </Button>
          )}
          {selectedActive ? (
            <Button
              variant="outline"
              onClick={() => cancelRun.mutate(undefined)}
              loading={cancelRun.isPending}
              data-testid="cancel-run-button"
            >
              <ForwardedIconComponent name="Square" className="h-4 w-4" />
              {t("evals.runs.cancel")}
            </Button>
          ) : (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  disabled={!rerun.canRerun || anyActive || rerunBusy}
                  loading={rerunBusy}
                  data-testid="rerun-button"
                >
                  <ForwardedIconComponent name="RotateCw" className="h-4 w-4" />
                  {t("evals.runs.rerun")}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  onClick={() => rerun.request(null)}
                  data-testid="rerun-latest"
                >
                  {t("evals.runs.rerunLatest")}
                </DropdownMenuItem>
                {selectedRun?.flow_version_id && (
                  <DropdownMenuItem
                    onClick={() => rerun.request(selectedRun.flow_version_id)}
                    data-testid="rerun-same-version"
                  >
                    {t("evals.runs.rerunSame", {
                      version: versionTag(selectedRun.flow_version_number, t),
                    })}
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </>
      }
      meta={
        evaluation && (
          <p className="text-sm text-muted-foreground">
            {t("evals.evaluations.meta", {
              flow: evaluation.flow_name ?? t("evals.evaluations.flowDeleted"),
              dataset:
                evaluation.dataset_name ??
                t("evals.evaluations.datasetDeleted"),
            })}
          </p>
        )
      }
    >
      <div className="flex flex-col gap-8 pb-10">
        <section aria-labelledby="runs-heading" className="flex flex-col gap-3">
          <h2 id="runs-heading" className="text-base font-semibold">
            {t("evals.runs.title")}
          </h2>
          {runs.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("evals.runs.empty")}
            </p>
          ) : (
            <RunsTable
              runs={runs}
              selectedRunId={selectedRunId}
              onSelect={selectRun}
            />
          )}
        </section>
        {selectedRun && (
          <section
            aria-labelledby="results-heading"
            className="flex flex-col gap-3"
          >
            <h2 id="results-heading" className="text-base font-semibold">
              {t("evals.results.title")}
            </h2>
            <RunResults key={selectedRun.id} run={selectedRun} />
          </section>
        )}
      </div>
      {rerun.confirmEstimate && (
        <ConfirmRunDialog
          open
          setOpen={(open) => !open && rerun.cancel()}
          estimate={rerun.confirmEstimate}
          loading={rerun.starting}
          onConfirm={rerun.confirm}
        />
      )}
    </EvalsPageShell>
  );
}
