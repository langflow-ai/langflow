import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useGetDatasets } from "@/controllers/API/queries/evals/use-datasets";
import { useGetFlowVersions } from "@/controllers/API/queries/flow-version";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { QUIET_SELECT_TRIGGER } from "@/pages/MainPage/pages/evalsPage/utils/styles";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { extractApiErrorMessages } from "@/utils/apiError";
import BaseModal from "../baseModal";
import ConfirmRunDialog from "./ConfirmRunDialog";
import EstimateCard from "./EstimateCard";
import EvaluationPreflight from "./EvaluationPreflight";
import FlowPicker from "./FlowPicker";
import ScorerFields from "./ScorerFields";
import { submitDecision } from "./submitDecision";
import { LATEST_VERSION, useEvaluateFlowForm } from "./useEvaluateFlowForm";

interface EvaluateFlowModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  /** Fixed when opened from the canvas; omitted on the Evaluations page, where the user picks a flow. */
  flowId?: string;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      {children}
    </section>
  );
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
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pickedFlowId, setPickedFlowId] = useState("");
  const flowId = fixedFlowId ?? pickedFlowId;
  const allFlows = useFlowsManagerStore((store) => store.flows);
  const flowOptions = (allFlows ?? []).filter((flow) => !flow.is_component);
  const form = useEvaluateFlowForm(flowId);
  const { state, set } = form;
  const pickFlow = (id: string) => {
    setPickedFlowId(id);
    set.setVersionId(LATEST_VERSION);
    set.setOutputVertexId("");
    set.setJudgeModel([]);
  };
  const { data: datasets } = useGetDatasets({ size: 200 }, { enabled: open });
  const { data: versions } = useGetFlowVersions(
    { flowId },
    { enabled: open && Boolean(flowId) },
  );
  const outputs = form.check.data?.output_vertices ?? [];
  const estimateFailed = form.estimate.isError;
  // A failed refetch keeps the previous numbers in `data`; they no longer describe this run.
  const estimate = estimateFailed ? undefined : form.estimate.data;
  const decision = submitDecision(form.estimate);

  const run = async () => {
    setSubmitting(true);
    try {
      const started = await form.createAndRun();
      setConfirmOpen(false);
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

  // A run that calls a model spends real money: show the numbers and ask once more.
  const handleSubmit = () => {
    if (!form.canSubmit || submitting || decision === "wait") return;
    if (decision === "confirm") {
      setConfirmOpen(true);
      return;
    }
    void run();
  };

  return (
    <>
      <BaseModal
        open={open}
        setOpen={setOpen}
        size="medium-h-full"
        onSubmit={handleSubmit}
      >
        <BaseModal.Header description={t("evals.evaluate.description")}>
          <ForwardedIconComponent
            name="FlaskConical"
            className="mr-2 h-4 w-4"
          />
          {t("evals.evaluate.title")}
        </BaseModal.Header>
        <BaseModal.Content>
          <div className="flex flex-col gap-6 px-1 pb-1">
            <Section title={t("evals.evaluate.whatToRun")}>
              {!fixedFlowId && (
                <div className="flex flex-col gap-2">
                  <Label htmlFor="evaluation-flow">
                    {t("evals.evaluate.flow")}
                  </Label>
                  <FlowPicker
                    id="evaluation-flow"
                    flows={flowOptions}
                    value={pickedFlowId}
                    onChange={pickFlow}
                  />
                </div>
              )}
              <div className="flex flex-col gap-2">
                <Label htmlFor="evaluation-name">
                  {t("evals.evaluate.name")}
                </Label>
                <Input
                  id="evaluation-name"
                  value={state.name}
                  maxLength={255}
                  placeholder={t("evals.evaluate.namePlaceholder")}
                  onChange={(event) => set.setName(event.target.value)}
                />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="evaluation-dataset">
                    {t("evals.evaluate.dataset")}
                  </Label>
                  <Select
                    value={state.datasetId}
                    onValueChange={set.setDatasetId}
                  >
                    <SelectTrigger
                      id="evaluation-dataset"
                      data-testid="evaluate-dataset"
                      className={QUIET_SELECT_TRIGGER}
                    >
                      <SelectValue
                        placeholder={t("evals.evaluate.chooseDataset")}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {(datasets?.items ?? []).map((dataset) => (
                        <SelectItem
                          key={dataset.id}
                          value={dataset.id}
                          disabled={dataset.item_count === 0}
                        >
                          {t("evals.evaluate.datasetOption", {
                            name: dataset.name,
                            count: dataset.item_count,
                          })}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {datasets && datasets.items.length === 0 && (
                    <button
                      type="button"
                      className="self-start text-xs underline underline-offset-4"
                      onClick={() => navigate("/assets/datasets")}
                    >
                      {t("evals.evaluate.createDatasetFirst")}
                    </button>
                  )}
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="evaluation-version">
                    {t("evals.evaluate.version")}
                  </Label>
                  <Select
                    value={state.versionId}
                    onValueChange={set.setVersionId}
                  >
                    <SelectTrigger
                      id="evaluation-version"
                      data-testid="evaluate-version"
                      className={QUIET_SELECT_TRIGGER}
                    >
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={LATEST_VERSION}>
                        {t("evals.evaluate.latestVersion")}
                      </SelectItem>
                      {(versions?.entries ?? []).map((version) => (
                        <SelectItem key={version.id} value={version.id}>
                          {version.description
                            ? `${version.version_tag} · ${version.description}`
                            : version.version_tag}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              {outputs.length > 1 && (
                <div className="flex flex-col gap-2">
                  <Label htmlFor="evaluation-output">
                    {t("evals.evaluate.output")}
                  </Label>
                  <Select
                    value={state.outputVertexId}
                    onValueChange={set.setOutputVertexId}
                  >
                    <SelectTrigger
                      id="evaluation-output"
                      className={QUIET_SELECT_TRIGGER}
                    >
                      <SelectValue
                        placeholder={t("evals.evaluate.chooseOutput")}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {outputs.map((output) => (
                        <SelectItem key={output.id} value={output.id}>
                          {output.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </Section>

            <Section title={t("evals.evaluate.howToScore")}>
              <ScorerFields
                flowId={flowId}
                selected={state.selected}
                onToggle={set.toggleScorer}
                judgeModel={state.judgeModel}
                onJudgeModel={set.setJudgeModel}
                rubric={state.rubric}
                onRubric={set.setRubric}
              />
              <div className="flex items-center gap-3">
                <Label htmlFor="evaluation-threshold" className="shrink-0">
                  {t("evals.evaluate.threshold")}
                </Label>
                <div className="w-24 shrink-0">
                  <Input
                    id="evaluation-threshold"
                    type="number"
                    min={0}
                    max={1}
                    step={0.05}
                    className="w-full"
                    value={state.threshold}
                    aria-describedby="evaluation-threshold-hint"
                    onChange={(event) => {
                      const value = Number(event.target.value);
                      if (!Number.isNaN(value)) {
                        set.setThreshold(Math.min(1, Math.max(0, value)));
                      }
                    }}
                  />
                </div>
                <span
                  id="evaluation-threshold-hint"
                  className="text-xs text-muted-foreground"
                >
                  {t("evals.evaluate.thresholdHint")}
                </span>
              </div>
            </Section>

            <Section title={t("evals.evaluate.beforeYouRun")}>
              <EvaluationPreflight
                report={form.check.data}
                failed={form.check.isError}
              />
              {form.judgeMissingModel ? (
                <div className="rounded-lg border border-dashed px-4 py-3 text-sm text-muted-foreground">
                  {t("evals.estimate.pickJudge")}
                </div>
              ) : (
                <EstimateCard
                  estimate={estimate}
                  loading={form.estimate.isFetching}
                  failed={estimateFailed}
                />
              )}
            </Section>
          </div>
        </BaseModal.Content>
        <BaseModal.Footer
          submit={{
            label: t("evals.evaluate.createAndRun"),
            loading: submitting && !confirmOpen,
            disabled: !form.canSubmit || submitting || decision === "wait",
            dataTestId: "evaluate-submit",
          }}
        />
      </BaseModal>
      {confirmOpen && (
        <ConfirmRunDialog
          open={confirmOpen}
          setOpen={setConfirmOpen}
          estimate={estimate}
          loading={submitting}
          onConfirm={() => void run()}
        />
      )}
    </>
  );
}
