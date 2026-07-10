import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import Loading from "@/components/ui/loading";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useGetTritonMetrics } from "@/controllers/API/queries/triton/use-get-triton-metrics";
import type { TritonModelStat } from "@/types/triton";

type MetricsTabProps = {
  serverId: string;
};

export function MetricsTab({ serverId }: MetricsTabProps) {
  const { t } = useTranslation();
  const [autoRefresh, setAutoRefresh] = useState(false);
  const { data, isLoading, isError, refetch } = useGetTritonMetrics(
    { serverId },
    { refetchInterval: autoRefresh ? 5000 : false },
  );

  if (isLoading) return <Loading />;

  if (isError) {
    return (
      <div className="flex flex-col items-center gap-3 py-8">
        <p className="text-sm text-destructive">
          {t("triton.detail.serverUnavailable")}
        </p>
        <Button variant="ghost" size="sm" onClick={() => refetch()}>
          {t("triton.detail.retry")}
        </Button>
      </div>
    );
  }

  const stats = data?.model_stats ?? [];

  if (stats.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        {t("triton.metrics.noMetrics")}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-4">
        <Button
          variant="ghost"
          size="xs"
          onClick={() => refetch()}
          data-testid="triton-metrics-refresh"
        >
          <ForwardedIconComponent name="RefreshCw" className="h-3.5 w-3.5" />
          {t("triton.detail.refresh")}
        </Button>
        <label className="flex items-center gap-2 text-xs">
          <Checkbox
            checked={autoRefresh}
            onCheckedChange={(v) => setAutoRefresh(v === true)}
            data-testid="triton-metrics-auto-refresh"
          />
          {t("triton.detail.autoRefresh")}
        </label>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("triton.metrics.column.metric")}</TableHead>
              <TableHead>Inferences</TableHead>
              <TableHead>Executions</TableHead>
              <TableHead>Success</TableHead>
              <TableHead>Fail</TableHead>
              <TableHead>Avg (ms)</TableHead>
              <TableHead>Last</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {stats.map((stat) => (
              <StatRow key={`${stat.name}-${stat.version ?? ""}`} stat={stat} />
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function StatRow({ stat }: { stat: TritonModelStat }) {
  const infStats = stat.inference_stats ?? {};
  const success = infStats.success;
  const fail = infStats.fail;
  const successCount = success?.count ?? 0;
  const failCount = fail?.count ?? 0;
  const avgMs =
    successCount > 0 && success?.ns
      ? (success.ns / successCount / 1_000_000).toFixed(2)
      : "—";

  return (
    <TableRow>
      <TableCell className="font-mono text-xs font-medium">
        {stat.name}
        {stat.version ? (
          <span className="text-muted-foreground"> v{stat.version}</span>
        ) : null}
      </TableCell>
      <TableCell className="font-mono text-xs">
        {stat.inference_count ?? 0}
      </TableCell>
      <TableCell className="font-mono text-xs">
        {stat.execution_count ?? 0}
      </TableCell>
      <TableCell className="font-mono text-xs">{successCount}</TableCell>
      <TableCell className="font-mono text-xs">{failCount}</TableCell>
      <TableCell className="font-mono text-xs">{avgMs}</TableCell>
      <TableCell className="font-mono text-xs text-muted-foreground">
        {formatTimestamp(stat.last_inference)}
      </TableCell>
    </TableRow>
  );
}

function formatTimestamp(ts?: number): string {
  if (!ts || ts === 0) return "—";
  return new Date(ts).toLocaleTimeString();
}
