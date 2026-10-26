import { useEffect, useState } from "react";
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
import {
  type RunStatus,
  TERMINAL_RUN_STATUSES,
} from "@/controllers/API/queries/evals/types";
import {
  exportUrl,
  RUN_POLL_MS,
  useCancelEvaluationRun,
  useEstimateEvaluation,
  useGetEvaluation,
  useGetEvaluationRun,
  useGetEvaluationRuns,
  useStartEvaluationRun,
} from "@/controllers/API/queries/evals/use-evaluations";
import { useDocumentTitle } from "@/hooks/use-document-title";
import ConfirmRunDialog from "@/modals/evaluateFlowModal/ConfirmRunDialog";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";
import BackLink from "./components/BackLink";
import EvalsPageShell from "./components/EvalsPageShell";
import RunResults from "./components/RunResults";
import RunsTable from "./components/RunsTable";
import { downloadCsv } from "./utils/download-csv";

export default function EvaluationDetailPage() {
  const { t } = useTranslation();
  const { evaluationId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const onError = (title: string) => (error: unknown) =>
    setErrorData({ title, list: extractApiErrorMessages(error) });

  const { data: evaluation } = useGetEvaluation({ evaluationId });
  const { data: runsPage } = useGetEvaluationRuns({ evaluationId }, {
    refetchInterval: (query: {
      state: { data?: { items: { status: RunStatus }[] } };
    }) =>
      query.state.data?.items.some(
        (run) => !TERMINAL_RUN_STATUSES.has(run.status),
      )
        ? RUN_POLL_MS
        : false,
  } as Parameters<typeof useGetEvaluationRuns>[1]);
  const runs = runsPage?.items ?? [];
  const anyActive = runs.some((run) => !TERMINAL_RUN_STATUSES.has(run.status));
  const selectedRunId = searchParams.get("run") ?? runs[0]?.id ?? null;
  const { data: selectedRun } = useGetEvaluationRun({
    runId: selectedRunId ?? "",
  });
  useDocumentTitle(evaluation?.name ?? t("evals.evaluations.title"));

  const selectRun = (runId: string) => setSearchParams({ run: runId });
  const startRun = useStartEvaluationRun(
    { evaluationId },
    {
      onSuccess: (run) => selectRun(run.id),
      onError: onError(t("evals.runs.startError")),
    },
  );
  const cancelRun = useCancelEvaluationRun(
    { runId: selectedRun?.id ?? "", evaluationId },
    { onError: onError(t("evals.runs.cancelError")) },
  );
  const selectedActive = Boolean(
    selectedRun && !TERMINAL_RUN_STATUSES.has(selectedRun.status),
  );
  const canRerun = Boolean(evaluation?.flow_id && evaluation?.dataset_id);
  const [pendingVersion, setPendingVersion] = useState<
    string | null | undefined
  >(undefined);
  const { data: rerunEstimate } = useEstimateEvaluation(
    {
      flowId: evaluation?.flow_id ?? "",
      datasetId: evaluation?.dataset_id ?? "",
      scorers: evaluation?.scorers ?? [],
    },
    { enabled: pendingVersion !== undefined && canRerun },
  );
  // Ask before spending tokens; a run with no model call starts right away.
  const requestRerun = (flowVersionId: string | null) => {
    setPendingVersion(flowVersionId);
  };
  useEffect(() => {
    if (pendingVersion === undefined || !rerunEstimate) return;
    if (rerunEstimate.llm_calls === 0) {
      startRun.mutate({ flowVersionId: pendingVersion });
      setPendingVersion(undefined);
    }
  }, [pendingVersion, rerunEstimate]);

  const handleExport = () => {
    if (!selectedRun) return;
    downloadCsv(exportUrl("run", selectedRun.id), "evaluation-run.csv").catch(
      onError(t("evals.exportError")),
    );
  };

  return (
    <EvalsPageShell
      title={evaluation?.name ?? ""}
      titleTestId="evaluation-detail-title"
      back={
        <BackLink
          to="/assets/evaluations"
          label={t("evals.evaluations.back")}
        />
      }
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
                  disabled={!canRerun || anyActive || startRun.isPending}
                  data-testid="rerun-button"
                >
                  <ForwardedIconComponent name="RotateCw" className="h-4 w-4" />
                  {t("evals.runs.rerun")}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  onClick={() => requestRerun(null)}
                  data-testid="rerun-latest"
                >
                  {t("evals.runs.rerunLatest")}
                </DropdownMenuItem>
                {selectedRun?.flow_version_id && (
                  <DropdownMenuItem
                    onClick={() => requestRerun(selectedRun.flow_version_id)}
                    data-testid="rerun-same-version"
                  >
                    {t("evals.runs.rerunSame", {
                      version: `v${selectedRun.flow_version_number}`,
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
            <RunResults run={selectedRun} />
          </section>
        )}
      </div>
      {rerunEstimate &&
        pendingVersion !== undefined &&
        rerunEstimate.llm_calls > 0 && (
          <ConfirmRunDialog
            open
            setOpen={(open) => !open && setPendingVersion(undefined)}
            estimate={rerunEstimate}
            loading={startRun.isPending}
            onConfirm={() => {
              startRun.mutate(
                { flowVersionId: pendingVersion },
                { onSettled: () => setPendingVersion(undefined) },
              );
            }}
          />
        )}
    </EvalsPageShell>
  );
}
