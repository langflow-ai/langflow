import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import type { RunEstimate } from "@/controllers/API/queries/evals/types";
import {
  formatRange,
  formatTokenCount,
  formatUsd,
} from "@/pages/MainPage/pages/evalsPage/utils/format";

function BreakdownRow({
  label,
  low,
  high,
  calls,
}: {
  label: string;
  low: number;
  high: number;
  calls: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="tabular-nums">
        {formatRange(formatTokenCount(low), formatTokenCount(high))}
        <span className="ml-2 text-xs text-muted-foreground">{calls}</span>
      </span>
    </div>
  );
}

export default function EstimateCard({
  estimate,
  loading,
  failed = false,
}: {
  estimate?: RunEstimate;
  loading: boolean;
  failed?: boolean;
}) {
  const { t } = useTranslation();
  if (failed) {
    return (
      <div
        className="rounded-lg border border-dashed px-4 py-3 text-sm text-muted-foreground"
        data-testid="evaluate-estimate-error"
      >
        {t("evals.estimate.error")}
      </div>
    );
  }
  if (!estimate) {
    return (
      <div className="rounded-lg border border-dashed px-4 py-3 text-sm text-muted-foreground">
        {loading
          ? t("evals.estimate.loading")
          : t("evals.estimate.pickDataset")}
      </div>
    );
  }
  const flowCalls = estimate.llm_calls - estimate.judge_calls;
  if (estimate.llm_calls === 0) {
    return (
      <div
        className="flex items-center gap-3 rounded-lg border px-4 py-3 text-sm"
        data-testid="evaluate-estimate"
      >
        <ForwardedIconComponent
          name="CircleCheck"
          aria-hidden="true"
          className="h-4 w-4 shrink-0 text-accent-emerald-foreground"
        />
        {t("evals.estimate.free", { count: estimate.items })}
      </div>
    );
  }
  return (
    <div
      className="flex flex-col gap-3 rounded-lg border px-4 py-3"
      data-testid="evaluate-estimate"
      aria-busy={loading}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{t("evals.estimate.title")}</span>
        <Badge variant="secondaryStatic" size="tag">
          {estimate.basis === "history"
            ? t("evals.estimate.fromHistory")
            : t("evals.estimate.rough")}
        </Badge>
      </div>
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="text-sm font-semibold tabular-nums">
          {t("evals.estimate.tokens", {
            range: formatRange(
              formatTokenCount(estimate.tokens_low),
              formatTokenCount(estimate.tokens_high),
            ),
          })}
        </span>
        <span className="text-sm font-semibold tabular-nums">
          {estimate.cost_low === null || estimate.cost_high === null
            ? t("evals.estimate.costUnknown")
            : formatRange(
                formatUsd(estimate.cost_low),
                formatUsd(estimate.cost_high),
              )}
        </span>
      </div>
      <div className="flex flex-col gap-1 border-t pt-3">
        {flowCalls > 0 && (
          <BreakdownRow
            label={t("evals.estimate.flow")}
            low={estimate.flow_tokens_low}
            high={estimate.flow_tokens_high}
            calls={t("evals.estimate.calls", { count: flowCalls })}
          />
        )}
        {estimate.judge_calls > 0 && (
          <BreakdownRow
            label={t("evals.estimate.judge")}
            low={estimate.judge_tokens_low}
            high={estimate.judge_tokens_high}
            calls={t("evals.estimate.calls", { count: estimate.judge_calls })}
          />
        )}
      </div>
      {estimate.has_agent && (
        <p className="text-xs text-muted-foreground">
          {t("evals.estimate.agentNote")}
        </p>
      )}
      {estimate.unpriced_models.length > 0 && (
        <p className="text-xs text-muted-foreground">
          {t("evals.estimate.unpriced", {
            models: estimate.unpriced_models.join(", "),
          })}
        </p>
      )}
    </div>
  );
}
