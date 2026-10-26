import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ModelInputComponent from "@/components/core/parameterRenderComponent/components/modelInputComponent";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent/types";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { ScorerType } from "@/controllers/API/queries/evals/types";
import { cn } from "@/utils/utils";
import { useJudgeModelOptions } from "./useJudgeModelOptions";

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
}

export default function ScorerFields({
  flowId,
  selected,
  onToggle,
  judgeModel,
  onJudgeModel,
  rubric,
  onRubric,
}: ScorerFieldsProps) {
  const { t } = useTranslation();
  const judgeOn = selected.has("llm_judge");
  const { options, ready } = useJudgeModelOptions(flowId, judgeOn);

  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="pb-2 text-sm font-medium">
        {t("evals.evaluate.scorers")}
      </legend>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {SCORERS.map(({ type, icon }) => {
          const checked = selected.has(type);
          return (
            <button
              key={type}
              type="button"
              role="checkbox"
              aria-checked={checked}
              id={`scorer-${type}`}
              data-testid={`scorer-${type}`}
              onClick={() => onToggle(type, !checked)}
              className={cn(
                "flex items-start gap-3 rounded-lg border px-3 py-3 text-left transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                checked && "border-primary",
              )}
            >
              <span
                aria-hidden="true"
                className={cn(
                  "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border border-muted-foreground",
                  checked &&
                    "border-primary bg-primary text-primary-foreground",
                )}
              >
                {checked && (
                  <ForwardedIconComponent name="Check" className="h-3 w-3" />
                )}
              </span>
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="flex items-center gap-1.5 text-sm font-medium">
                  <ForwardedIconComponent
                    name={icon}
                    aria-hidden="true"
                    className="h-3.5 w-3.5 text-muted-foreground"
                  />
                  {t(`evals.scorers.${type}`)}
                </span>
                <span className="text-xs text-muted-foreground">
                  {t(`evals.scorers.${type}Hint`)}
                </span>
              </span>
            </button>
          );
        })}
      </div>
      {judgeOn && (
        <div className="flex flex-col gap-4 rounded-lg border px-4 py-4">
          <div className="flex flex-col gap-2 [&_button]:h-10">
            <Label htmlFor="judge-model">
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
              aria-label={t("evals.evaluate.judgeModel")}
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
        </div>
      )}
    </fieldset>
  );
}
