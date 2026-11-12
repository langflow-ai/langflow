import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import InfoHint from "@/pages/MainPage/pages/evalsPage/components/InfoHint";
import CollapsibleSection from "./CollapsibleSection";
import {
  JUDGE_MAX_OUTPUT_TOKENS_CEILING,
  JUDGE_MAX_RUN_OUTPUT_TOKENS_CEILING,
} from "./judgeLimits";

export interface JudgeLimits {
  /** Both budgets are kept as typed so a field can be cleared while editing; validated before submit. */
  maxOutputTokens: string;
  maxRunOutputTokens: string;
  stopOnOutputLimit: boolean;
}

interface JudgeLimitFieldsProps {
  value: JudgeLimits;
  onChange: (value: JudgeLimits) => void;
  rowInvalid: boolean;
  runInvalid: boolean;
  /** The chosen judge thinks before answering, and that thinking uses the same budget. */
  reasoningModel: boolean;
}

interface BudgetFieldProps {
  id: string;
  label: string;
  /** An (i) next to the label, for what the label leaves out. */
  info?: ReactNode;
  error: string;
  invalid: boolean;
  max: number;
  value: string;
  onChange: (value: string) => void;
}

function BudgetField({
  id,
  label,
  info,
  error,
  invalid,
  max,
  value,
  onChange,
}: BudgetFieldProps) {
  const errorId = `${id}-error`;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-1.5">
        <Label htmlFor={id}>{label}</Label>
        {info}
      </div>
      <div className="w-36">
        <Input
          id={id}
          data-testid={id}
          type="number"
          inputMode="numeric"
          min={1}
          max={max}
          step={1}
          className="w-full"
          value={value}
          aria-invalid={invalid}
          aria-describedby={invalid ? errorId : undefined}
          onChange={(event) => onChange(event.target.value)}
        />
      </div>
      {invalid && (
        <span id={errorId} className="text-xs text-destructive">
          {error}
        </span>
      )}
    </div>
  );
}

export default function JudgeLimitFields({
  value,
  onChange,
  rowInvalid,
  runInvalid,
  reasoningModel,
}: JudgeLimitFieldsProps) {
  const { t } = useTranslation();
  const summary = t("evals.evaluate.judgeLimitsSummary", {
    row: value.maxOutputTokens || "—",
    run: value.maxRunOutputTokens || "—",
    stop: t(
      value.stopOnOutputLimit
        ? "evals.evaluate.judgeLimitsStops"
        : "evals.evaluate.judgeLimitsContinues",
    ),
  });
  const rowLabel = t("evals.evaluate.judgeMaxTokens");
  const stopLabel = t("evals.evaluate.judgeStopOnLimit");

  return (
    <CollapsibleSection
      id="judge-limits"
      title={t("evals.evaluate.judgeLimits")}
      summary={summary}
      // An invalid value must never hide behind a collapsed section.
      forceOpen={rowInvalid || runInvalid}
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <BudgetField
          id="judge-max-tokens"
          label={rowLabel}
          info={
            reasoningModel && (
              <InfoHint
                hint={t("evals.evaluate.judgeMaxTokensReasoningHint")}
                label={t("evals.infoLabel", { name: rowLabel })}
                testId="judge-max-tokens-info"
              />
            )
          }
          error={t("evals.evaluate.judgeMaxTokensInvalid", {
            max: JUDGE_MAX_OUTPUT_TOKENS_CEILING.toLocaleString(),
          })}
          invalid={rowInvalid}
          max={JUDGE_MAX_OUTPUT_TOKENS_CEILING}
          value={value.maxOutputTokens}
          onChange={(maxOutputTokens) =>
            onChange({ ...value, maxOutputTokens })
          }
        />
        <BudgetField
          id="judge-max-run-tokens"
          label={t("evals.evaluate.judgeMaxRunTokens")}
          error={t("evals.evaluate.judgeMaxRunTokensInvalid", {
            max: JUDGE_MAX_RUN_OUTPUT_TOKENS_CEILING.toLocaleString(),
          })}
          invalid={runInvalid}
          max={JUDGE_MAX_RUN_OUTPUT_TOKENS_CEILING}
          value={value.maxRunOutputTokens}
          onChange={(maxRunOutputTokens) =>
            onChange({ ...value, maxRunOutputTokens })
          }
        />
      </div>
      <div className="flex items-center gap-2">
        <Checkbox
          id="judge-stop-on-limit"
          data-testid="judge-stop-on-limit"
          checked={value.stopOnOutputLimit}
          onCheckedChange={(checked) =>
            onChange({ ...value, stopOnOutputLimit: checked === true })
          }
        />
        <Label htmlFor="judge-stop-on-limit" className="font-normal">
          {stopLabel}
        </Label>
        <InfoHint
          hint={t(
            value.stopOnOutputLimit
              ? "evals.evaluate.judgeStopOnLimitOnHint"
              : "evals.evaluate.judgeStopOnLimitOffHint",
          )}
          label={t("evals.infoLabel", { name: stopLabel })}
          testId="judge-stop-on-limit-info"
        />
      </div>
    </CollapsibleSection>
  );
}
