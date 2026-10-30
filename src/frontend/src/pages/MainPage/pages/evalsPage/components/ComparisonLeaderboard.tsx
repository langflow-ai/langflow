import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/utils/utils";
import type { ComparisonEntry } from "../utils/comparison";
import {
  formatDuration,
  formatPercent,
  formatRange,
  formatRatio,
  formatTokenCount,
  formatUsd,
} from "../utils/format";
import RunStatusBadge from "./RunStatusBadge";
import VariantLabel, { variantName } from "./VariantLabel";

interface ComparisonLeaderboardProps {
  /** Ranked versions first, then the ones still running or not run. */
  entries: ComparisonEntry[];
  cheapest: ComparisonEntry | null;
  fastest: ComparisonEntry | null;
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
}

function PassRateCell({ entry }: { entry: ComparisonEntry }) {
  const { t } = useTranslation();
  if (entry.passRate === null) return <>—</>;
  return (
    <div className="ml-auto flex w-28 flex-col items-end gap-1">
      <span className="flex items-center gap-1.5 font-medium">
        {(entry.matchesTop || entry.tiedWithTop) && (
          <Badge
            variant="secondaryStatic"
            size="tag"
            title={
              entry.matchesTop
                ? t("evals.compare.tieLegend")
                : t("evals.compare.tiedHint")
            }
          >
            {entry.matchesTop
              ? t("evals.compare.tie")
              : t("evals.compare.tied")}
          </Badge>
        )}
        {formatPercent(entry.passRate)}
      </span>
      <span
        className="h-1 w-full overflow-hidden rounded-full bg-muted"
        aria-hidden="true"
      >
        <span
          className="block h-full rounded-full bg-primary"
          style={{ width: `${Math.round(entry.passRate * 100)}%` }}
        />
      </span>
      {entry.interval && (
        <span className="text-xs text-muted-foreground">
          {formatRange(
            formatPercent(entry.interval[0]),
            formatPercent(entry.interval[1]),
          )}
        </span>
      )}
    </div>
  );
}

/** A column's value, bold with a tag when it leads, else how many times the leader's it is. */
function LeadCell({
  value,
  leads,
  ratio,
  tag,
  extra,
}: {
  value: string;
  leads: boolean;
  ratio: string | null;
  tag: string;
  extra?: string;
}) {
  const { t } = useTranslation();
  return (
    <span className="flex flex-col items-end">
      <span className={cn(leads && "font-semibold")}>{value}</span>
      {(leads || ratio) && (
        <span className="text-xs text-muted-foreground">
          {leads ? tag : t("evals.compare.timesMin", { ratio })}
        </span>
      )}
      {extra && <span className="text-xs text-muted-foreground">{extra}</span>}
    </span>
  );
}

export default function ComparisonLeaderboard({
  entries,
  cheapest,
  fastest,
  selectedRunId,
  onSelect,
}: ComparisonLeaderboardProps) {
  const { t } = useTranslation();
  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table aria-label={t("evals.compare.leaderboard")}>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">{t("evals.compare.rank")}</TableHead>
            <TableHead>{t("evals.compare.models")}</TableHead>
            <TableHead className="text-right">{t("evals.runs.rows")}</TableHead>
            <TableHead className="text-right">
              {t("evals.compare.errors")}
            </TableHead>
            <TableHead className="text-right">{t("evals.passRate")}</TableHead>
            <TableHead className="text-right">{t("evals.cost")}</TableHead>
            <TableHead className="text-right">
              {t("evals.compare.costPerRow")}
            </TableHead>
            <TableHead className="text-right">
              {t("evals.results.p50")}
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map((entry) => {
            const run = entry.run;
            const selected = run !== null && run.id === selectedRunId;
            const label = (
              <VariantLabel index={entry.index} overrides={entry.overrides} />
            );
            return (
              <TableRow
                key={entry.index}
                data-testid="comparison-row"
                aria-selected={selected}
                className={cn(selected && "bg-muted")}
              >
                <TableCell className="font-semibold tabular-nums">
                  {entry.rank ?? "—"}
                </TableCell>
                <TableCell className="max-w-72">
                  <div className="flex flex-wrap items-center gap-2">
                    {run ? (
                      <button
                        type="button"
                        className="min-w-0 rounded-sm text-left underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        onClick={() => onSelect(run.id)}
                        aria-label={t("evals.compare.open", {
                          version: entry.index + 1,
                          models: variantName(entry.overrides, t),
                        })}
                      >
                        {label}
                      </button>
                    ) : (
                      label
                    )}
                    {entry.state !== "completed" &&
                      (run ? (
                        <RunStatusBadge status={run.status} />
                      ) : (
                        <Badge variant="gray" size="tag">
                          {t(`evals.compare.state.${entry.state}`)}
                        </Badge>
                      ))}
                  </div>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {run
                    ? t("evals.compare.ratio", {
                        part: formatTokenCount(entry.completed),
                        total: formatTokenCount(entry.total),
                      })
                    : "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {run ? formatTokenCount(entry.errored) : "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  <PassRateCell entry={entry} />
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  <LeadCell
                    value={formatUsd(entry.cost, { precise: true })}
                    leads={entry === cheapest}
                    ratio={
                      entry.rank !== null
                        ? formatRatio(entry.cost, cheapest?.cost)
                        : null
                    }
                    tag={t("evals.compare.cheapestTag")}
                  />
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatUsd(entry.costPerRow, { precise: true })}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  <LeadCell
                    value={formatDuration(entry.p50)}
                    leads={entry === fastest}
                    ratio={
                      entry.rank !== null
                        ? formatRatio(entry.p50, fastest?.p50)
                        : null
                    }
                    tag={t("evals.compare.fastestTag")}
                    extra={
                      entry.p90 !== null
                        ? t("evals.compare.p90", {
                            value: formatDuration(entry.p90),
                          })
                        : undefined
                    }
                  />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
