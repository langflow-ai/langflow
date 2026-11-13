import { useTranslation } from "react-i18next";
import type {
  SafetyCheck,
  SafetySummary,
} from "@/controllers/API/queries/evals/types";
import { cn } from "@/utils/utils";
import { formatPercent } from "../utils/format";

interface SafetyKpisProps {
  summary: SafetySummary;
  /** The check whose flagged rows the table shows, or null for every row. */
  active: SafetyCheck | null;
  onSelect: (check: SafetyCheck | null) => void;
}

/** The judge's safety rates for the run; each check filters the table to the rows it flagged. */
export default function SafetyKpis({
  summary,
  active,
  onSelect,
}: SafetyKpisProps) {
  const { t } = useTranslation();
  const { attacks } = summary;

  return (
    <section
      aria-labelledby="run-safety-title"
      className="flex flex-col gap-2 rounded-lg border px-4 py-3"
      data-testid="run-safety"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id="run-safety-title" className="text-sm font-medium">
          {t("evals.safety.title")}
        </h3>
        <span className="text-xs text-muted-foreground">
          {t("evals.safety.judged", { count: summary.judged })}
          {attacks.total > 0 &&
            ` · ${t("evals.safety.resisted", {
              resisted: attacks.resisted,
              total: attacks.total,
            })}`}
        </span>
      </div>
      <div
        role="group"
        aria-label={t("evals.safety.filterLabel")}
        className="flex flex-wrap gap-2"
      >
        <span className="flex items-baseline gap-1.5 rounded-md bg-muted px-3 py-1.5 text-sm">
          <span className="text-muted-foreground">
            {t("evals.safety.safe")}
          </span>
          <span className="font-semibold tabular-nums">
            {formatPercent(summary.safe)}
          </span>
        </span>
        {summary.checks.map((check) => {
          const pressed = active === check;
          const rate = summary.rates[check] ?? null;
          return (
            <button
              key={check}
              type="button"
              aria-pressed={pressed}
              onClick={() => onSelect(pressed ? null : check)}
              data-testid={`run-safety-${check}`}
              className={cn(
                "flex items-baseline gap-1.5 rounded-md border px-3 py-1.5 text-sm transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                pressed && "border-foreground bg-muted",
              )}
            >
              <span className="text-muted-foreground">
                {t(`evals.safety.check.${check}`)}
              </span>
              <span
                className={cn(
                  "font-semibold tabular-nums",
                  rate ? "text-destructive" : undefined,
                )}
              >
                {formatPercent(rate)}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
