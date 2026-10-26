import { useTranslation } from "react-i18next";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { EvaluationRun } from "@/controllers/API/queries/evals/types";
import { cn } from "@/utils/utils";
import {
  formatDelta,
  formatPercent,
  formatRunDate,
  formatTokenCount,
  formatUsd,
} from "../utils/format";
import RunStatusBadge from "./RunStatusBadge";

interface RunsTableProps {
  runs: EvaluationRun[];
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
}

function versionLabel(run: EvaluationRun, latestLabel: string): string {
  const tag =
    run.flow_version_number === null ? "—" : `v${run.flow_version_number}`;
  return run.flow_version_source === "latest" ? `${latestLabel} → ${tag}` : tag;
}

export default function RunsTable({
  runs,
  selectedRunId,
  onSelect,
}: RunsTableProps) {
  const { t } = useTranslation();
  return (
    <Table aria-label={t("evals.runs.title")}>
      <TableHeader>
        <TableRow>
          <TableHead>{t("evals.runs.started")}</TableHead>
          <TableHead>{t("evals.runs.status")}</TableHead>
          <TableHead>{t("evals.runs.version")}</TableHead>
          <TableHead className="text-right">{t("evals.passRate")}</TableHead>
          <TableHead className="text-right">{t("evals.tokens")}</TableHead>
          <TableHead className="text-right">{t("evals.cost")}</TableHead>
          <TableHead className="text-right">{t("evals.runs.rows")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run, index) => {
          const previous = runs[index + 1];
          const tokenDelta = formatDelta(
            run.summary?.tokens.total,
            previous?.summary?.tokens.total,
          );
          const selected = run.id === selectedRunId;
          return (
            <TableRow
              key={run.id}
              data-testid="run-row"
              aria-selected={selected}
              className={cn(selected && "bg-muted")}
            >
              <TableCell>
                <button
                  type="button"
                  className="underline-offset-4 hover:underline focus-visible:underline"
                  onClick={() => onSelect(run.id)}
                  aria-label={t("evals.runs.open", {
                    date: formatRunDate(run.created_at),
                  })}
                >
                  {formatRunDate(run.created_at)}
                </button>
              </TableCell>
              <TableCell>
                <RunStatusBadge status={run.status} />
              </TableCell>
              <TableCell>{versionLabel(run, t("evals.latest"))}</TableCell>
              <TableCell className="text-right">
                {formatPercent(run.summary?.pass_rate)}
              </TableCell>
              <TableCell className="text-right">
                {formatTokenCount(run.summary?.tokens.total)}
                {tokenDelta && (
                  <span className="ml-1 text-xs text-muted-foreground">
                    ({tokenDelta})
                  </span>
                )}
              </TableCell>
              <TableCell className="text-right">
                {formatUsd(run.summary?.cost_usd.total)}
              </TableCell>
              <TableCell className="text-right">
                {run.completed_items}/{run.total_items}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
