import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  type PaginatedIngestionRunResponse,
  useGetIngestionRuns,
} from "@/controllers/API/queries/knowledge-bases/use-get-ingestion-runs";
import IngestionRunDetailModal from "./IngestionRunDetailModal";

interface IngestionRunsSectionProps {
  kbName: string;
}

const TERMINAL_RUN_STATUSES = new Set([
  "succeeded",
  "partial",
  "failed",
  "cancelled",
]);
const RUN_POLL_INTERVAL_MS = 5000;

const STATUS_STYLES: Record<string, string> = {
  succeeded:
    "bg-accent-emerald text-accent-emerald-foreground border-accent-emerald",
  partial: "bg-warning text-warning-foreground border-warning",
  failed: "bg-error-red text-accent-red-foreground border-error-red-border",
  cancelled: "bg-muted text-muted-foreground border-border",
  running:
    "bg-accent-indigo text-accent-indigo-foreground border-accent-indigo",
  pending: "bg-muted text-muted-foreground border-border",
};

const SOURCE_TYPE_LABELS: Record<string, string> = {
  file_upload: "knowledge.ingestionSourceFileUpload",
  folder: "knowledge.ingestionSourceFolder",
  template: "knowledge.ingestionSourceTemplate",
  google_drive: "knowledge.ingestionSourceGoogleDrive",
  s3: "knowledge.ingestionSourceS3",
  onedrive: "knowledge.ingestionSourceOneDrive",
  sharepoint: "knowledge.ingestionSourceSharePoint",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatRelativeTime(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diffSec = Math.max(0, Math.floor((now - then) / 1000));
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}

const IngestionRunsSection = ({ kbName }: IngestionRunsSectionProps) => {
  const { t } = useTranslation();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const { data, isLoading, isError } = useGetIngestionRuns(
    {
      kb_name: kbName,
      page: 1,
      limit: 10,
    },
    {
      refetchOnMount: "always",
      refetchIntervalInBackground: false,
      refetchInterval: (query) => {
        const runs = (
          query.state.data as PaginatedIngestionRunResponse | undefined
        )?.runs;
        if (!runs?.length) return false;
        const hasActive = runs.some(
          (run) => !TERMINAL_RUN_STATUSES.has(run.status),
        );
        return hasActive ? RUN_POLL_INTERVAL_MS : false;
      },
    },
  );

  return (
    <div className="space-y-3 px-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium">{t("knowledge.ingestionRuns")}</h4>
        {data?.total ? (
          <span className="text-xs text-muted-foreground">
            {data.total} total
          </span>
        ) : null}
      </div>

      {isLoading && (
        <div className="text-sm text-muted-foreground">
          {t("knowledge.loadingRuns")}
        </div>
      )}
      {isError && (
        <div className="text-sm text-destructive">
          Unable to load ingestion runs.
        </div>
      )}
      {!isLoading && !isError && data?.runs.length === 0 && (
        <div className="text-sm text-muted-foreground">
          No ingestion runs yet. Upload a file or ingest a folder to see history
          here.
        </div>
      )}

      <div className="flex flex-col gap-2">
        {data?.runs.map((run) => {
          const statusClass =
            STATUS_STYLES[run.status] ?? STATUS_STYLES.pending;
          const sourceLabel = SOURCE_TYPE_LABELS[run.source_type]
            ? t(SOURCE_TYPE_LABELS[run.source_type])
            : run.source_type;
          return (
            <button
              key={run.id}
              type="button"
              onClick={() => setSelectedRunId(run.id)}
              className="flex w-full flex-col gap-2 rounded-md border border-border bg-card p-3 text-left transition hover:border-primary/40 hover:bg-muted/30"
            >
              <div className="flex items-center justify-between gap-2">
                <span
                  className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${statusClass}`}
                >
                  {run.status}
                </span>
                <span className="text-xs text-muted-foreground">
                  {formatRelativeTime(run.started_at)}
                </span>
              </div>
              <span className="truncate text-sm font-medium">
                {sourceLabel}
              </span>
              <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <ForwardedIconComponent
                    name="CircleCheck"
                    className="h-3 w-3 text-accent-emerald-foreground"
                  />
                  {run.succeeded}
                </span>
                {run.failed > 0 && (
                  <span className="flex items-center gap-1">
                    <ForwardedIconComponent
                      name="CircleAlert"
                      className="h-3 w-3 text-destructive"
                    />
                    {run.failed}
                  </span>
                )}
                {run.skipped > 0 && (
                  <span className="flex items-center gap-1">
                    <ForwardedIconComponent
                      name="CircleMinus"
                      className="h-3 w-3 text-muted-foreground"
                    />
                    {run.skipped}
                  </span>
                )}
                <span>·</span>
                <span>{run.chunks_created} chunks</span>
                {run.total_bytes > 0 && (
                  <>
                    <span>·</span>
                    <span>{formatBytes(run.total_bytes)}</span>
                  </>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {selectedRunId && (
        <IngestionRunDetailModal
          kbName={kbName}
          runId={selectedRunId}
          onClose={() => setSelectedRunId(null)}
        />
      )}
    </div>
  );
};

export default IngestionRunsSection;
