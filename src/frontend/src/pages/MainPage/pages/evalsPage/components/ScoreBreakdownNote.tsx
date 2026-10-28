import { useTranslation } from "react-i18next";
import type {
  EvaluationResult,
  ScorerSpec,
} from "@/controllers/API/queries/evals/types";
import { cn } from "@/utils/utils";
import { formatFormula, scoreBreakdown } from "../utils/score-breakdown";

interface ScoreBreakdownNoteProps {
  result: EvaluationResult;
  scorers: ScorerSpec[];
  threshold: number;
}

/** Shows the arithmetic behind Passed/Failed, so a verdict never looks arbitrary. */
export default function ScoreBreakdownNote({
  result,
  scorers,
  threshold,
}: ScoreBreakdownNoteProps) {
  const { t } = useTranslation();
  const breakdown = scoreBreakdown(result, scorers, threshold);
  const scorerLabel = (name: string) =>
    t(`evals.scorers.${name}`, { defaultValue: name });

  return (
    <div
      className="flex flex-col gap-1 rounded-lg border bg-muted/40 px-3 py-2 text-sm"
      data-testid="score-breakdown"
    >
      <span className="text-xs font-medium text-muted-foreground">
        {t("evals.results.breakdown.title")}
      </span>
      {breakdown.kind === "errored" && (
        <span>{t("evals.results.breakdown.errored")}</span>
      )}
      {breakdown.kind === "undecided" && (
        <span>{t("evals.results.breakdown.undecided")}</span>
      )}
      {breakdown.kind === "scored" && (
        <>
          <span className="tabular-nums">
            {t("evals.results.breakdown.formula", {
              formula: formatFormula(breakdown.terms),
              average: breakdown.average.toFixed(2),
            })}
          </span>
          <span
            className={cn(
              "font-medium",
              breakdown.passed
                ? "text-accent-emerald-foreground"
                : "text-destructive",
            )}
          >
            {t(
              breakdown.passed
                ? "evals.results.breakdown.passed"
                : "evals.results.breakdown.failed",
              { threshold: breakdown.threshold.toFixed(2) },
            )}
          </span>
        </>
      )}
      {breakdown.kind !== "errored" && breakdown.skipped.length > 0 && (
        <span className="text-xs text-muted-foreground">
          {t("evals.results.breakdown.skipped", {
            names: breakdown.skipped.map(scorerLabel).join(", "),
          })}
        </span>
      )}
    </div>
  );
}
