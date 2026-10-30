import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  useGetDatasetItems,
  useGetDatasets,
} from "@/controllers/API/queries/evals/use-datasets";
import { useGetFlowVersions } from "@/controllers/API/queries/flow-version";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { DIALOG_CONTAINER } from "@/pages/MainPage/pages/evalsPage/utils/styles";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { extractApiErrorMessages } from "@/utils/apiError";
import { modelKindOfField } from "@/utils/model-kind";
import BaseModal from "../baseModal";
import EvaluateStepper, { type EvaluateStep } from "./EvaluateStepper";
import ModelOverrides from "./ModelOverrides";
import ReviewStep from "./ReviewStep";
import ScorerFields from "./ScorerFields";
import SetupStep from "./SetupStep";
import { submitDecision } from "./submitDecision";
import ThresholdField from "./ThresholdField";
import { LATEST_VERSION, useEvaluateFlowForm } from "./useEvaluateFlowForm";

type StepKey = "setup" | "scoring" | "models" | "review";
const PREVIEW_ROWS = 3;

function flowTime(flow: { updated_at?: string; date_created?: string }) {
  return Date.parse(flow.updated_at ?? flow.date_created ?? "") || 0;
}

interface EvaluateFlowModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  /** Fixed when opened from the canvas; omitted on the Evaluations page, where the user picks a flow. */
  flowId?: string;
}

export default function EvaluateFlowModal({
  open,
  setOpen,
  flowId: fixedFlowId,
}: EvaluateFlowModalProps) {
  const { t } = useTranslation();
  const navigate = useCustomNavigate();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [submitting, setSubmitting] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [pickedFlowId, setPickedFlowId] = useState("");
  const flowId = fixedFlowId ?? pickedFlowId;
  const allFlows = useFlowsManagerStore((store) => store.flows);
  // Most recently changed first: the flow being worked on is usually the one to evaluate.
  const flowOptions = (allFlows ?? [])
    .filter((flow) => !flow.is_component)
    .sort((a, b) => flowTime(b) - flowTime(a));
  const form = useEvaluateFlowForm(flowId);
  const { state, set } = form;
  const pickFlow = (id: string) => {
    setPickedFlowId(id);
    set.setVersionId(LATEST_VERSION);
    set.setOutputVertexId("");
    set.setJudgeModel([]);
    set.resetModels();
  };
  const { data: datasets } = useGetDatasets({ size: 200 }, { enabled: open });
  const { data: versions } = useGetFlowVersions(
    { flowId },
    { enabled: open && Boolean(flowId) },
  );
  const report = form.check.data;
  const { data: preview } = useGetDatasetItems(
    { datasetId: state.datasetId, size: PREVIEW_ROWS },
    { enabled: open && Boolean(state.datasetId) },
  );
  const pickers = report?.model_pickers ?? [];
  const outputs = report?.output_vertices ?? [];
  const hasModels = pickers.some((picker) =>
    modelKindOfField({ model_type: picker.model_type }),
  );
  const estimateFailed = form.estimate.isError;
  // A failed refetch keeps the previous numbers in `data`; they no longer describe this run.
  const estimate = estimateFailed ? undefined : form.estimate.data;
  const decision = submitDecision(form.estimate);

  const keys: StepKey[] = hasModels
    ? ["setup", "scoring", "models", "review"]
    : ["setup", "scoring", "review"];
  const steps: EvaluateStep[] = keys.map((key) => ({
    key,
    label: t(`evals.evaluate.step.${key}`),
  }));
  // A step list that loses the models step (another flow) must not leave the index past the end.
  const current = Math.min(stepIndex, keys.length - 1);
  const stepKey = keys[current];
  const stepReady: Record<StepKey, boolean> = {
    setup:
      Boolean(flowId && state.datasetId && report) &&
      report?.blocking.length === 0 &&
      (outputs.length <= 1 || Boolean(state.outputVertexId)),
    scoring:
      form.scorers.length > 0 &&
      !form.judgeMissingModel &&
      !form.judgeRowBudgetInvalid &&
      !form.judgeRunBudgetInvalid,
    models: !form.modelsMissing,
    review: form.canSubmit && decision !== "wait",
  };
  const isLast = current === keys.length - 1;

  const run = async () => {
    setSubmitting(true);
    try {
      const started = await form.createAndRun();
      setOpen(false);
      navigate(
        `/assets/evaluations/${started.evaluation_id}?run=${started.id}`,
      );
    } catch (error) {
      setErrorData({
        title: t("evals.evaluate.error"),
        list: extractApiErrorMessages(error),
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Enter and the main button both move forward; the review step is the confirmation before a run.
  const handleSubmit = () => {
    if (!stepReady[stepKey] || submitting) return;
    if (!isLast) {
      setStepIndex(current + 1);
      return;
    }
    void run();
  };

  const datasetName =
    datasets?.items.find((dataset) => dataset.id === state.datasetId)?.name ??
    "";
  const flowName =
    flowOptions.find((flow) => flow.id === flowId)?.name ??
    allFlows?.find((flow) => flow.id === flowId)?.name ??
    "";

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="medium-h-full"
      // Compared versions sit side by side; every other step keeps the narrower form.
      width={
        stepKey === "models" && form.comparing
          ? "min(920px, 96vw)"
          : "min(720px, 96vw)"
      }
      className={DIALOG_CONTAINER}
      onSubmit={handleSubmit}
    >
      <BaseModal.Header description={t("evals.evaluate.description")}>
        <ForwardedIconComponent name="FlaskConical" className="mr-2 h-4 w-4" />
        {t("evals.evaluate.title")}
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex flex-col gap-5 px-1 pb-1">
          <EvaluateStepper
            steps={steps}
            current={current}
            onSelect={setStepIndex}
          />
          <section
            aria-labelledby="evaluate-step-title"
            className="flex flex-col gap-4"
            data-testid={`evaluate-step-panel-${stepKey}`}
          >
            <div className="flex flex-col gap-1">
              {/* The stepper already shows the step's name; the heading names the section for screen readers. */}
              <h3 id="evaluate-step-title" className="sr-only">
                {t(`evals.evaluate.step.${stepKey}`)}
              </h3>
              <p className="text-sm text-muted-foreground">
                {t(`evals.evaluate.stepHint.${stepKey}`)}
              </p>
            </div>
            {stepKey === "setup" && (
              <SetupStep
                flowFixed={Boolean(fixedFlowId)}
                flowOptions={flowOptions}
                flowId={flowId}
                onPickFlow={pickFlow}
                datasets={datasets?.items}
                datasetId={state.datasetId}
                onDataset={set.setDatasetId}
                outputs={outputs}
                outputVertexId={state.outputVertexId}
                onOutput={set.setOutputVertexId}
                report={report}
                checkFailed={form.check.isError}
                onCreateDataset={() => navigate("/assets/datasets")}
                previewItems={preview?.items ?? []}
                previewTotal={preview?.total ?? 0}
                models={hasModels ? pickers.length : 0}
              />
            )}
            {stepKey === "scoring" && (
              <>
                <ScorerFields
                  flowId={flowId}
                  selected={state.selected}
                  onToggle={set.toggleScorer}
                  judgeModel={state.judgeModel}
                  onJudgeModel={set.setJudgeModel}
                  rubric={state.rubric}
                  onRubric={set.setRubric}
                  judgeLimits={state.judgeLimits}
                  onJudgeLimits={set.setJudgeLimits}
                  judgeRowBudgetInvalid={form.judgeRowBudgetInvalid}
                  judgeRunBudgetInvalid={form.judgeRunBudgetInvalid}
                  safetyChecks={state.safetyChecks}
                  onSafetyChecks={set.setSafetyChecks}
                />
                <ThresholdField
                  value={state.threshold}
                  onChange={set.setThreshold}
                />
              </>
            )}
            {stepKey === "models" && (
              <ModelOverrides
                flowId={flowId}
                pickers={pickers}
                versions={state.modelVersions}
                onChange={set.chooseModel}
                onDuplicate={set.duplicateModelVersion}
                onRemove={set.removeModelVersion}
              />
            )}
            {stepKey === "review" && (
              <ReviewStep
                flowName={flowName}
                datasetName={datasetName}
                outputName={
                  outputs.length > 1
                    ? outputs.find(
                        (output) => output.id === state.outputVertexId,
                      )?.name
                    : undefined
                }
                scorers={form.scorers}
                threshold={state.threshold}
                variants={form.variantOverrides}
                pickers={hasModels ? pickers : []}
                name={state.name}
                onName={set.setName}
                versionId={state.versionId}
                onVersion={set.setVersionId}
                versions={versions?.entries ?? []}
                estimate={estimate}
                estimateLoading={form.estimate.isFetching}
                estimateFailed={estimateFailed}
              />
            )}
          </section>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer
        submit={{
          label: !isLast
            ? t("evals.evaluate.next")
            : form.comparing
              ? t("evals.compare.submit", {
                  count: state.modelVersions.length,
                })
              : t("evals.evaluate.createAndRun"),
          loading: submitting,
          disabled: !stepReady[stepKey] || submitting,
          dataTestId: isLast ? "evaluate-submit" : "evaluate-next",
        }}
      >
        {current > 0 ? (
          <Button
            variant="ghost"
            type="button"
            onClick={() => setStepIndex(current - 1)}
            data-testid="evaluate-back"
          >
            <ForwardedIconComponent name="ArrowLeft" className="h-4 w-4" />
            {t("evals.evaluate.back")}
          </Button>
        ) : undefined}
      </BaseModal.Footer>
    </BaseModal>
  );
}
