import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  hint: string;
  error: string;
  invalid: boolean;
  max: number;
  value: string;
  onChange: (value: string) => void;
}

function BudgetField({
  id,
  label,
  hint,
  error,
  invalid,
  max,
  value,
  onChange,
}: BudgetFieldProps) {
  const hintId = `${id}-hint`;
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>
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
          aria-describedby={hintId}
          onChange={(event) => onChange(event.target.value)}
        />
      </div>
      <span
        id={hintId}
        className={
          invalid ? "text-xs text-destructive" : "text-xs text-muted-foreground"
        }
      >
        {invalid ? error : hint}
      </span>
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
  const [open, setOpen] = useState(false);
  // An invalid value must never hide behind a collapsed section.
  const expanded = open || rowInvalid || runInvalid;
  const summary = t("evals.evaluate.judgeLimitsSummary", {
    row: value.maxOutputTokens || "—",
    run: value.maxRunOutputTokens || "—",
    stop: t(
      value.stopOnOutputLimit
        ? "evals.evaluate.judgeLimitsStops"
        : "evals.evaluate.judgeLimitsContinues",
    ),
  });

  return (
    <div className="flex flex-col gap-3">
      <button
        type="button"
        data-testid="judge-limits-toggle"
        aria-expanded={expanded}
        aria-controls="judge-limits-panel"
        onClick={() => setOpen(!expanded)}
        className="flex w-full items-center gap-2 rounded-md text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ForwardedIconComponent
          name="ChevronRight"
          aria-hidden="true"
          className={
            expanded
              ? "h-4 w-4 shrink-0 rotate-90 text-muted-foreground transition-transform motion-reduce:transition-none"
              : "h-4 w-4 shrink-0 text-muted-foreground transition-transform motion-reduce:transition-none"
          }
        />
        <span className="text-sm font-medium">
          {t("evals.evaluate.judgeLimits")}
        </span>
        {!expanded && (
          <span className="truncate text-xs text-muted-foreground">
            {summary}
          </span>
        )}
      </button>
      {expanded && (
        <div id="judge-limits-panel" className="flex flex-col gap-3 pl-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <BudgetField
              id="judge-max-tokens"
              label={t("evals.evaluate.judgeMaxTokens")}
              hint={t(
                reasoningModel
                  ? "evals.evaluate.judgeMaxTokensReasoningHint"
                  : "evals.evaluate.judgeMaxTokensHint",
              )}
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
              hint={t("evals.evaluate.judgeMaxRunTokensHint")}
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
          <div className="flex items-start gap-2">
            <Checkbox
              id="judge-stop-on-limit"
              data-testid="judge-stop-on-limit"
              checked={value.stopOnOutputLimit}
              aria-describedby="judge-stop-on-limit-hint"
              onCheckedChange={(checked) =>
                onChange({ ...value, stopOnOutputLimit: checked === true })
              }
              className="mt-0.5"
            />
            <div className="flex flex-col gap-0.5">
              <Label htmlFor="judge-stop-on-limit" className="font-normal">
                {t("evals.evaluate.judgeStopOnLimit")}
              </Label>
              <span
                id="judge-stop-on-limit-hint"
                className="text-xs text-muted-foreground"
              >
                {t(
                  value.stopOnOutputLimit
                    ? "evals.evaluate.judgeStopOnLimitOnHint"
                    : "evals.evaluate.judgeStopOnLimitOffHint",
                )}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
