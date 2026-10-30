import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { EvaluationRun } from "@/controllers/API/queries/evals/types";
import { buildComparison, type ComparisonEntry } from "../utils/comparison";
import { formatDuration, formatPercent, formatUsd } from "../utils/format";
import ComparisonLeaderboard from "./ComparisonLeaderboard";
import ComparisonSafety from "./ComparisonSafety";
import Kpi from "./Kpi";
import VariantLabel from "./VariantLabel";
import VariantMarker from "./VariantMarker";

interface ModelComparisonProps {
  runs: readonly EvaluationRun[];
  comparisonId: string;
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
}

function Winner({
  entry,
  tied = 0,
  empty,
}: {
  entry: ComparisonEntry | null;
  tied?: number;
  /** What to say when no version qualifies; "not decided yet" by default. */
  empty?: string;
}) {
  const { t } = useTranslation();
  if (!entry) return <>{empty ?? t("evals.compare.noWinner")}</>;
  return (
    <>
      <VariantLabel
        index={entry.index}
        overrides={entry.overrides}
        detail={false}
      />
      {tied > 0 && (
        <span className="shrink-0">
          {t("evals.compare.alsoTied", { count: tied })}
        </span>
      )}
    </>
  );
}

/** Every version sharing the top pass rate: naming one would crown a tie-break, not accuracy. */
function TiedWinners({ entries }: { entries: ComparisonEntry[] }) {
  const { t } = useTranslation();
  return (
    <>
      <span className="flex -space-x-1">
        {entries.map((entry) => (
          <VariantMarker key={entry.index} index={entry.index} />
        ))}
      </span>
      {t("evals.compare.tiedCount", { count: entries.length })}
    </>
  );
}

function KpiIcon({ name }: { name: string }) {
  return (
    <ForwardedIconComponent
      name={name}
      aria-hidden="true"
      className="h-3.5 w-3.5"
    />
  );
}

/** The versions of one comparison side by side: who wins on pass rate, cost and speed, then the ranking. */
export default function ModelComparison({
  runs,
  comparisonId,
  selectedRunId,
  onSelect,
}: ModelComparisonProps) {
  const { t } = useTranslation();
  const comparison = useMemo(
    () => buildComparison(runs, comparisonId),
    [runs, comparisonId],
  );
  if (!comparison) return null;
  const { entries, ranked, mostAccurate, cheapest, fastest } = comparison;
  const unranked = entries.filter((entry) => entry.rank === null);
  const matching = ranked.filter((entry) => entry.matchesTop);
  const total = entries.length;

  return (
    <section
      aria-labelledby="comparison-heading"
      className="flex flex-col gap-3"
      data-testid="model-comparison"
    >
      <div className="flex flex-col gap-1">
        {/* The Comparison tab already names this view; the heading labels the section for screen readers. */}
        <h2 id="comparison-heading" className="sr-only">
          {t("evals.compare.title")}
        </h2>
        <p className="text-sm text-muted-foreground">
          {t("evals.compare.description")}
        </p>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          testId="comparison-most-accurate"
          icon={<KpiIcon name="Trophy" />}
          label={t("evals.compare.mostAccurate")}
          value={formatPercent(mostAccurate?.passRate)}
          hint={
            matching.length > 0 && mostAccurate ? (
              <TiedWinners entries={[mostAccurate, ...matching]} />
            ) : (
              <Winner
                entry={mostAccurate}
                tied={ranked.filter((entry) => entry.tiedWithTop).length}
              />
            )
          }
        />
        <Kpi
          testId="comparison-cheapest"
          icon={<KpiIcon name="DollarSign" />}
          label={t("evals.compare.cheapest")}
          value={formatUsd(cheapest?.cost, { precise: true })}
          hint={
            <Winner
              entry={cheapest}
              // Every version finished and none has a price: waiting will not decide it.
              empty={
                comparison.finished === total
                  ? t("evals.estimate.costUnknown")
                  : undefined
              }
            />
          }
        />
        <Kpi
          testId="comparison-fastest"
          icon={<KpiIcon name="Timer" />}
          label={t("evals.compare.fastest")}
          value={formatDuration(fastest?.p50)}
          hint={<Winner entry={fastest} />}
        />
        <Kpi
          testId="comparison-total-cost"
          icon={<KpiIcon name="Coins" />}
          label={t("evals.compare.totalCost")}
          value={formatUsd(comparison.totalCost, { precise: true })}
          hint={t("evals.compare.finished", {
            done: comparison.finished,
            total,
          })}
        />
      </div>
      <ComparisonLeaderboard
        entries={[...ranked, ...unranked]}
        cheapest={cheapest}
        fastest={fastest}
        selectedRunId={selectedRunId}
        onSelect={onSelect}
      />
      <ComparisonSafety entries={[...ranked, ...unranked]} />
    </section>
  );
}
