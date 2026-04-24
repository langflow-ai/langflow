import { useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useGetIngestionRuns } from "@/controllers/API/queries/knowledge-bases/use-get-ingestion-runs";
import IngestionRunDetailModal from "./IngestionRunDetailModal";

interface IngestionRunsSectionProps {
  kbName: string;
}

const STATUS_STYLES: Record<string, string> = {
  succeeded: "bg-emerald-50 text-emerald-700 border-emerald-200",
  partial: "bg-amber-50 text-amber-700 border-amber-200",
  failed: "bg-rose-50 text-rose-700 border-rose-200",
  cancelled: "bg-slate-50 text-slate-600 border-slate-200",
  running: "bg-sky-50 text-sky-700 border-sky-200",
  pending: "bg-slate-50 text-slate-600 border-slate-200",
};

const SOURCE_TYPE_LABELS: Record<string, string> = {
  file_upload: "File Upload",
  folder: "Folder",
  template: "Flow Template",
  google_drive: "Google Drive",
  s3: "AWS S3",
  onedrive: "OneDrive",
  sharepoint: "SharePoint",
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
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const { data, isLoading, isError } = useGetIngestionRuns({
    kb_name: kbName,
    page: 1,
    limit: 10,
  });

  return (
    <div className="space-y-3 px-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium">Ingestion Runs</h4>
        {data?.total ? (
          <span className="text-xs text-muted-foreground">
            {data.total} total
          </span>
        ) : null}
      </div>

      {isLoading && (
        <div className="text-sm text-muted-foreground">Loading runs…</div>
      )}
      {isError && (
        <div className="text-sm text-rose-600">
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
          const sourceLabel =
            SOURCE_TYPE_LABELS[run.source_type] ?? run.source_type;
          return (
            <button
              key={run.id}
              type="button"
              onClick={() => setSelectedRunId(run.id)}
              className="flex w-full flex-col gap-1 rounded-md border border-border bg-card p-2 text-left transition hover:border-primary/40 hover:bg-muted/30"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 truncate">
                  <span
                    className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${statusClass}`}
                  >
                    {run.status}
                  </span>
                  <span className="truncate text-xs font-medium">
                    {sourceLabel}
                  </span>
                </div>
                <span className="text-xs text-muted-foreground">
                  {formatRelativeTime(run.started_at)}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <ForwardedIconComponent
                    name="CircleCheck"
                    className="h-3 w-3 text-emerald-600"
                  />
                  {run.succeeded}
                </span>
                {run.failed > 0 && (
                  <span className="flex items-center gap-1">
                    <ForwardedIconComponent
                      name="CircleAlert"
                      className="h-3 w-3 text-rose-600"
                    />
                    {run.failed}
                  </span>
                )}
                {run.skipped > 0 && (
                  <span className="flex items-center gap-1">
                    <ForwardedIconComponent
                      name="CircleMinus"
                      className="h-3 w-3 text-slate-500"
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
