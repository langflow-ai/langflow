import { type ReactNode, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  type EvaluationRun,
  TERMINAL_RUN_STATUSES,
} from "@/controllers/API/queries/evals/types";
import {
  formatDuration,
  formatPercent,
  formatRange,
  formatScore,
  formatTokenCount,
  formatUsd,
} from "../utils/format";

function Kpi({
  label,
  value,
  hint,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-lg border px-4 py-3">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="truncate text-xl font-semibold tabular-nums">
        {value}
      </span>
      {hint && (
        <span className="truncate text-xs text-muted-foreground">{hint}</span>
      )}
    </div>
  );
}

export default function RunKpis({ run }: { run: EvaluationRun }) {
  const { t } = useTranslation();
  const summary = run.summary;
  const active = !TERMINAL_RUN_STATUSES.has(run.status);
  const progress = run.total_items
    ? Math.round((run.completed_items / run.total_items) * 100)
    : 0;
  const scores = Object.entries(summary?.scores ?? {});
  const estimate = run.estimate;
  const [announcement, setAnnouncement] = useState("");
  const previousStatus = useRef(run.status);
  // WCAG 4.1.3: a run ending is a status change screen readers must hear without moving focus.
  useEffect(() => {
    const wasActive = !TERMINAL_RUN_STATUSES.has(previousStatus.current);
    previousStatus.current = run.status;
    if (wasActive && TERMINAL_RUN_STATUSES.has(run.status)) {
      setAnnouncement(
        t("evals.results.runEnded", {
          status: t(`evals.status.${run.status}`),
        }),
      );
    }
  }, [run.status, t]);

  return (
    <div className="flex flex-col gap-3">
      <p
        role="status"
        aria-live="polite"
        className="sr-only"
        data-testid="run-status-announcement"
      >
        {announcement}
      </p>
      {active && (
        <div className="flex flex-col gap-2 rounded-lg border px-4 py-3">
          <div className="flex items-center justify-between text-sm">
            <span>{t("evals.results.progressLabel")}</span>
            <span className="tabular-nums text-muted-foreground">
              {t("evals.results.progress", {
                done: run.completed_items,
                total: run.total_items,
              })}
            </span>
          </div>
          <div
            className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
            aria-label={t("evals.results.progressLabel")}
          >
            <div
              className="h-full rounded-full bg-primary transition-[width] duration-500 motion-reduce:transition-none"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}
      {run.error && (
        <p
          role="alert"
          className="rounded-lg border border-destructive/40 px-4 py-3 text-sm text-destructive"
        >
          {run.error}
        </p>
      )}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi
          label={t("evals.passRate")}
          value={formatPercent(summary?.pass_rate)}
          hint={t("evals.results.passedOf", {
            passed: run.passed_items,
            total: run.completed_items,
          })}
        />
        <Kpi
          label={t("evals.tokens")}
          value={formatTokenCount(summary?.tokens.total)}
          hint={
            estimate?.tokens_low != null &&
            estimate.tokens_high != null &&
            !active
              ? t("evals.results.estimated", {
                  range: formatRange(
                    formatTokenCount(estimate.tokens_low),
                    formatTokenCount(estimate.tokens_high),
                  ),
                })
              : undefined
          }
        />
        <Kpi
          label={t("evals.cost")}
          value={formatUsd(summary?.cost_usd.total)}
        />
        <Kpi
          label={t("evals.results.p50")}
          value={formatDuration(summary?.duration_ms.p50)}
          hint={
            run.failed_items > 0
              ? t("evals.results.erroredCount", { count: run.failed_items })
              : undefined
          }
        />
      </div>
      {scores.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {scores.map(([name, stats]) => (
            <span
              key={name}
              className="rounded-md border px-2.5 py-1 text-xs text-muted-foreground"
            >
              {name}{" "}
              <span className="font-medium tabular-nums text-foreground">
                {formatScore(stats.mean)}
              </span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
