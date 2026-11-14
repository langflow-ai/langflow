import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ModelInputComponent from "@/components/core/parameterRenderComponent/components/modelInputComponent";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent/types";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type {
  SafetyCheck,
  ScorerType,
} from "@/controllers/API/queries/evals/types";
import InfoHint from "@/pages/MainPage/pages/evalsPage/components/InfoHint";
import { cn } from "@/utils/utils";
import JudgeLimitFields, { type JudgeLimits } from "./JudgeLimitFields";
import { isReasoningModel } from "./judgeLimits";
import SafetyCheckFields from "./SafetyCheckFields";
import { useModelOptions } from "./useModelOptions";

const SCORERS: { type: ScorerType; icon: string }[] = [
  { type: "exact_match", icon: "Equal" },
  { type: "contains", icon: "TextSearch" },
  { type: "similarity", icon: "Percent" },
  { type: "llm_judge", icon: "Sparkle" },
];

interface ScorerFieldsProps {
  flowId: string;
  selected: ReadonlySet<ScorerType>;
  onToggle: (type: ScorerType, on: boolean) => void;
  judgeModel: ModelOption[];
  onJudgeModel: (value: ModelOption[]) => void;
  rubric: string;
  onRubric: (value: string) => void;
  judgeLimits: JudgeLimits;
  onJudgeLimits: (value: JudgeLimits) => void;
  judgeRowBudgetInvalid: boolean;
  judgeRunBudgetInvalid: boolean;
  safetyChecks: readonly SafetyCheck[];
  onSafetyChecks: (value: SafetyCheck[]) => void;
}

export default function ScorerFields({
  flowId,
  selected,
  onToggle,
  judgeModel,
  onJudgeModel,
  rubric,
  onRubric,
  judgeLimits,
  onJudgeLimits,
  judgeRowBudgetInvalid,
  judgeRunBudgetInvalid,
  safetyChecks,
  onSafetyChecks,
}: ScorerFieldsProps) {
  const { t } = useTranslation();
  const judgeOn = selected.has("llm_judge");
  const { options, ready } = useModelOptions(flowId, judgeOn);

  return (
    // A fieldset is min-content wide by default; min-w-0 lets a long line truncate instead of widening the dialog.
    <fieldset className="flex min-w-0 flex-col gap-3">
      <legend className="pb-2 text-sm font-medium">
        {t("evals.evaluate.scorers")}
      </legend>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {SCORERS.map(({ type, icon }) => {
          const checked = selected.has(type);
          const name = t(`evals.scorers.${type}`);
          return (
            // The checkbox stretches over the whole card (its ::after), and the (i) sits above it:
            // a button cannot hold another button.
            <div
              key={type}
              className={cn(
                "relative flex items-center gap-1.5 rounded-lg border px-3 py-3 transition-colors hover:bg-muted",
                checked && "border-primary",
              )}
            >
              <button
                type="button"
                role="checkbox"
                aria-checked={checked}
                id={`scorer-${type}`}
                data-testid={`scorer-${type}`}
                onClick={() => onToggle(type, !checked)}
                className="flex min-w-0 items-center gap-3 text-left after:absolute after:inset-0 after:rounded-lg focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring"
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    "flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border border-muted-foreground",
                    checked &&
                      "border-primary bg-primary text-primary-foreground",
                  )}
                >
                  {checked && (
                    <ForwardedIconComponent name="Check" className="h-3 w-3" />
                  )}
                </span>
                <span className="flex items-center gap-1.5 text-sm font-medium">
                  <ForwardedIconComponent
                    name={icon}
                    aria-hidden="true"
                    className="h-3.5 w-3.5 text-muted-foreground"
                  />
                  {name}
                </span>
              </button>
              <span className="relative z-10 flex">
                <InfoHint
                  hint={t(`evals.scorers.${type}Hint`)}
                  label={t("evals.infoLabel", { name })}
                  testId={`scorer-${type}-info`}
                />
              </span>
            </div>
          );
        })}
      </div>
      {judgeOn && (
        <div className="flex flex-col gap-4 rounded-lg border px-4 py-4">
          <div className="flex flex-col gap-2 [&_button]:h-10">
            <Label id="judge-model-label">
              {t("evals.evaluate.judgeModel")}
            </Label>
            <ModelInputComponent
              id="judge-model"
              value={judgeModel}
              editNode={false}
              disabled={!ready}
              handleOnNewValue={({ value }) => onJudgeModel(value)}
              options={options}
              providerScope={{ flowId }}
              placeholder={t("evals.evaluate.judgeModelPlaceholder")}
              modelType="llm"
              showEmptyState
              ariaLabelledBy="judge-model-label"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="judge-rubric">{t("evals.evaluate.rubric")}</Label>
            <Textarea
              id="judge-rubric"
              value={rubric}
              maxLength={4000}
              rows={2}
              placeholder={t("evals.evaluate.rubricPlaceholder")}
              onChange={(event) => onRubric(event.target.value)}
            />
          </div>
          <SafetyCheckFields value={safetyChecks} onChange={onSafetyChecks} />
          <JudgeLimitFields
            value={judgeLimits}
            onChange={onJudgeLimits}
            rowInvalid={judgeRowBudgetInvalid}
            runInvalid={judgeRunBudgetInvalid}
            reasoningModel={isReasoningModel(judgeModel[0]?.metadata)}
          />
        </div>
      )}
    </fieldset>
  );
}
