import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type {
  Evaluation,
  ModelVariant,
  RunEstimate,
} from "@/controllers/API/queries/evals/types";
import {
  useEstimateEvaluation,
  useStartEvaluationRun,
} from "@/controllers/API/queries/evals/use-evaluations";
import useAlertStore from "@/stores/alertStore";
import { extractApiErrorMessages } from "@/utils/apiError";

/** A requested re-run: `null` runs the latest draft, a string a pinned version; variants re-run a comparison. */
interface PendingRerun {
  flowVersionId: string | null;
  variants: ModelVariant[];
}

/**
 * Re-runs an evaluation, asking first when the run spends tokens. While the
 * estimate loads the re-run is pending; a failed estimate is reported and the
 * request dropped, so nothing ever starts without the numbers.
 */
export function useRerun(
  evaluation: Evaluation | undefined,
  onStarted: (runId: string) => void,
) {
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [pendingRerun, setPendingRerun] = useState<PendingRerun | null>(null);
  const pending = pendingRerun !== null;
  const canRerun = Boolean(evaluation?.flow_id && evaluation?.dataset_id);

  const startRun = useStartEvaluationRun(
    { evaluationId: evaluation?.id ?? "" },
    {
      onSuccess: (run) => onStarted(run.id),
      onError: (error) =>
        setErrorData({
          title: t("evals.runs.startError"),
          list: extractApiErrorMessages(error),
        }),
    },
  );
  const estimate = useEstimateEvaluation(
    {
      flowId: evaluation?.flow_id ?? "",
      datasetId: evaluation?.dataset_id ?? "",
      scorers: evaluation?.scorers ?? [],
      variants: pendingRerun?.variants ?? [],
    },
    { enabled: pending && canRerun },
  );
  const settled =
    pending && !estimate.isFetching && !estimate.isPlaceholderData;
  const { mutate } = startRun;

  useEffect(() => {
    if (!settled) return;
    if (estimate.isError) {
      setErrorData({
        title: t("evals.estimate.error"),
        list: extractApiErrorMessages(estimate.error),
      });
      setPendingRerun(null);
      return;
    }
    if (estimate.data && estimate.data.llm_calls === 0 && pendingRerun) {
      mutate(pendingRerun);
      setPendingRerun(null);
    }
  }, [
    settled,
    estimate.isError,
    estimate.error,
    estimate.data,
    pendingRerun,
    mutate,
    setErrorData,
    t,
  ]);

  const confirmEstimate: RunEstimate | undefined =
    settled && !estimate.isError && estimate.data && estimate.data.llm_calls > 0
      ? estimate.data
      : undefined;

  return {
    canRerun,
    request: (flowVersionId: string | null, variants: ModelVariant[] = []) =>
      setPendingRerun({ flowVersionId, variants }),
    cancel: () => setPendingRerun(null),
    confirm: () => {
      if (!pendingRerun) return;
      mutate(pendingRerun, { onSettled: () => setPendingRerun(null) });
    },
    confirmEstimate,
    estimating: pending && !settled,
    starting: startRun.isPending,
  };
}
