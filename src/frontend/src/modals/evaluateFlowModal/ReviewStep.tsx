import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type {
  FlowModelPicker,
  ModelOverride,
  RunEstimate,
  ScorerSpec,
} from "@/controllers/API/queries/evals/types";
import VariantMarker from "@/pages/MainPage/pages/evalsPage/components/VariantMarker";
import type { FlowVersionEntry } from "@/types/flow/version";
import EstimateCard from "./EstimateCard";
import { effectiveModelNames } from "./modelOverrideUtils";
import RunSettings from "./RunSettings";

interface ReviewStepProps {
  flowName: string;
  datasetName: string;
  outputName?: string;
  scorers: ScorerSpec[];
  threshold: number;
  /** One entry per run; several mean a comparison. */
  variants: ModelOverride[][];
  pickers: readonly FlowModelPicker[];
  name: string;
  onName: (value: string) => void;
  versionId: string;
  onVersion: (value: string) => void;
  versions: FlowVersionEntry[];
  estimate?: RunEstimate;
  estimateLoading: boolean;
  estimateFailed: boolean;
}

function Row({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[8rem_1fr] gap-3 py-2 text-sm">
      <dt className="text-muted-foreground">{term}</dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}

/** Everything the run will do and what it may cost, before it starts: the last look, not another dialog. */
export default function ReviewStep({
  flowName,
  datasetName,
  outputName,
  scorers,
  threshold,
  variants,
  pickers,
  name,
  onName,
  versionId,
  onVersion,
  versions,
  estimate,
  estimateLoading,
  estimateFailed,
}: ReviewStepProps) {
  const { t } = useTranslation();
  const judge = scorers.find((scorer) => scorer.type === "llm_judge");
  const scoring = scorers
    .map((scorer) => t(`evals.scorers.${scorer.type}`))
    .join(", ");

  return (
    <div className="flex flex-col gap-5">
      <dl
        className="divide-y rounded-lg border px-4"
        data-testid="evaluate-review"
      >
        <Row term={t("evals.evaluate.flow")}>{flowName}</Row>
        <Row term={t("evals.evaluate.dataset")}>{datasetName}</Row>
        {outputName && (
          <Row term={t("evals.evaluate.output")}>{outputName}</Row>
        )}
        <Row term={t("evals.evaluate.scorers")}>
          {scoring}
          {judge?.config?.model?.[0] && (
            <span className="text-muted-foreground">
              {" · "}
              {t("evals.evaluate.reviewJudge", {
                model: judge.config.model[0].name,
              })}
            </span>
          )}
          <span className="block text-xs text-muted-foreground">
            {t("evals.evaluate.reviewThreshold", { threshold })}
          </span>
        </Row>
        {pickers.length > 0 && (
          <Row term={t("evals.evaluate.models")}>
            <ul className="flex flex-col gap-1.5">
              {variants.map((overrides, index) => (
                // A read-only summary that never reorders: the version's place is its identity.
                <li key={index} className="flex min-w-0 items-center gap-2">
                  {variants.length > 1 && <VariantMarker index={index} />}
                  <span className="truncate">
                    {effectiveModelNames(pickers, overrides).join(" + ")}
                  </span>
                </li>
              ))}
            </ul>
          </Row>
        )}
      </dl>
      <RunSettings
        name={name}
        onName={onName}
        versionId={versionId}
        onVersion={onVersion}
        versions={versions}
      />
      <EstimateCard
        estimate={estimate}
        loading={estimateLoading}
        failed={estimateFailed}
      />
      {(estimateFailed || (estimate?.llm_calls ?? 0) > 0) && (
        <p
          className="text-xs text-muted-foreground"
          data-testid="evaluate-spend-notice"
        >
          {t("evals.evaluate.spendNotice")}
        </p>
      )}
    </div>
  );
}
