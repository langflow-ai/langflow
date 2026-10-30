import { useTranslation } from "react-i18next";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type {
  Dataset,
  DatasetItem,
  FlowCheckReport,
} from "@/controllers/API/queries/evals/types";
import { QUIET_SELECT_TRIGGER } from "@/pages/MainPage/pages/evalsPage/utils/styles";
import { cn } from "@/utils/utils";

// Long lists scroll inside the space left on screen instead of running off it.
const LIST_HEIGHT =
  "max-h-[min(20rem,var(--radix-select-content-available-height))]";

import DatasetPreview from "./DatasetPreview";
import EvaluationPreflight from "./EvaluationPreflight";
import FlowPicker from "./FlowPicker";
import FlowReadiness from "./FlowReadiness";

interface SetupStepProps {
  /** Opened from the canvas: the flow is given, only the dataset is chosen. */
  flowFixed: boolean;
  flowOptions: { id: string; name: string }[];
  flowId: string;
  onPickFlow: (id: string) => void;
  datasets: Dataset[] | undefined;
  datasetId: string;
  onDataset: (id: string) => void;
  outputs: { id: string; name: string }[];
  outputVertexId: string;
  onOutput: (id: string) => void;
  report: FlowCheckReport | undefined;
  checkFailed: boolean;
  onCreateDataset: () => void;
  previewItems: DatasetItem[];
  previewTotal: number;
  /** Model pickers the Models step can swap. */
  models: number;
}

/** What to evaluate: the flow, the dataset its rows come from, and whether the flow can run at all. */
export default function SetupStep({
  flowFixed,
  flowOptions,
  flowId,
  onPickFlow,
  datasets,
  datasetId,
  onDataset,
  outputs,
  outputVertexId,
  onOutput,
  report,
  checkFailed,
  onCreateDataset,
  previewItems,
  previewTotal,
  models,
}: SetupStepProps) {
  const { t } = useTranslation();
  const hasDatasets = (datasets?.length ?? 0) > 0;
  return (
    <div className="flex flex-col gap-5">
      <div className={cn("grid gap-4", !flowFixed && "md:grid-cols-2")}>
        {!flowFixed && (
          <div className="flex flex-col gap-2">
            <Label htmlFor="evaluation-flow">{t("evals.evaluate.flow")}</Label>
            <FlowPicker
              id="evaluation-flow"
              flows={flowOptions}
              value={flowId}
              onChange={onPickFlow}
            />
          </div>
        )}
        <div className="flex flex-col gap-2">
          <Label htmlFor="evaluation-dataset">
            {t("evals.evaluate.dataset")}
          </Label>
          <Select
            value={datasetId}
            onValueChange={onDataset}
            disabled={!hasDatasets}
          >
            <SelectTrigger
              id="evaluation-dataset"
              data-testid="evaluate-dataset"
              className={cn("h-9", QUIET_SELECT_TRIGGER)}
            >
              <SelectValue placeholder={t("evals.evaluate.chooseDataset")} />
            </SelectTrigger>
            <SelectContent className={LIST_HEIGHT}>
              {(datasets ?? []).map((dataset) => (
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
          {datasets && !hasDatasets && (
            <button
              type="button"
              className="self-start text-xs underline underline-offset-4"
              onClick={onCreateDataset}
            >
              {t("evals.evaluate.createDatasetFirst")}
            </button>
          )}
        </div>
      </div>
      {outputs.length > 1 && (
        <div className="flex flex-col gap-2">
          <Label htmlFor="evaluation-output">
            {t("evals.evaluate.output")}
          </Label>
          <Select value={outputVertexId} onValueChange={onOutput}>
            <SelectTrigger
              id="evaluation-output"
              className={cn("h-9", QUIET_SELECT_TRIGGER)}
            >
              <SelectValue placeholder={t("evals.evaluate.chooseOutput")} />
            </SelectTrigger>
            <SelectContent className={LIST_HEIGHT}>
              {outputs.map((output) => (
                <SelectItem key={output.id} value={output.id}>
                  {output.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {flowId && report && (
        <FlowReadiness
          report={report}
          outputName={
            outputs.find((output) => output.id === outputVertexId)?.name ??
            (outputs.length === 1 ? outputs[0].name : undefined)
          }
          models={models}
        />
      )}
      {flowId && <EvaluationPreflight report={report} failed={checkFailed} />}
      {datasetId && (
        <DatasetPreview items={previewItems} total={previewTotal} />
      )}
    </div>
  );
}
