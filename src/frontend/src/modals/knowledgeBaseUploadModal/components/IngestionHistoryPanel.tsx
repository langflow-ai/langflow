import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useGetIngestionRuns } from "@/controllers/API/queries/knowledge-bases/use-get-ingestion-runs";
import { cn } from "@/utils/utils";

interface IngestionHistoryPanelProps {
  kbName: string;
}

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

const HISTORY_LIMIT = 10;

function formatRelativeTime(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diffSec = Math.max(0, Math.floor((now - then) / 1000));
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}

export function IngestionHistoryPanel({ kbName }: IngestionHistoryPanelProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(true);
  const { data, isLoading, isError } = useGetIngestionRuns(
    { kb_name: kbName, page: 1, limit: HISTORY_LIMIT },
    { staleTime: 0, refetchOnMount: "always" },
  );

  const total = data?.total ?? 0;
  const runs = data?.runs ?? [];

  return (
    <div
      className="flex flex-col gap-2 rounded-md border border-border bg-muted/40 p-3"
      data-testid="kb-ingestion-history-panel"
    >
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={() => setExpanded((v) => !v)}
        data-testid="kb-ingestion-history-toggle"
      >
        <div className="flex items-center gap-2">
          <ForwardedIconComponent
            name="History"
            className="h-4 w-4 text-muted-foreground"
          />
          <span className="text-sm font-medium">
            {t("knowledge.previouslyIngested")}
          </span>
          {total > 0 && (
            <span className="text-xs text-muted-foreground">({total})</span>
          )}
        </div>
        <ForwardedIconComponent
          name={expanded ? "ChevronUp" : "ChevronDown"}
          className="h-4 w-4 text-muted-foreground"
        />
      </button>

      {expanded && (
        <div
          className={cn(
            "flex flex-col gap-2",
            runs.length > 0 && "max-h-[200px] overflow-y-auto pr-1",
          )}
        >
          {isLoading && (
            <div
              className="text-xs text-muted-foreground"
              data-testid="kb-ingestion-history-loading"
            >
              Loading history…
            </div>
          )}
          {isError && !isLoading && (
            <div className="text-xs text-destructive">
              Unable to load ingestion history.
            </div>
          )}
          {!isLoading && !isError && runs.length === 0 && (
            <div
              className="text-xs text-muted-foreground"
              data-testid="kb-ingestion-history-empty"
            >
              No sources ingested yet. The first upload will appear here.
            </div>
          )}
          {runs.map((run) => {
            const statusClass =
              STATUS_STYLES[run.status] ?? STATUS_STYLES.pending;
            const typeLabel = SOURCE_TYPE_LABELS[run.source_type]
              ? t(SOURCE_TYPE_LABELS[run.source_type])
              : run.source_type;
            const trimmedName = run.source_name?.trim();
            const primaryLabel = trimmedName || typeLabel;
            const showTypeSubtitle = !!trimmedName;
            return (
              <div
                key={run.id}
                className="flex flex-col gap-2 rounded-md border border-border bg-background p-3"
                data-testid="kb-ingestion-history-row"
              >
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={cn(
                      "rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide",
                      statusClass,
                    )}
                  >
                    {run.status}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {formatRelativeTime(run.started_at)}
                  </span>
                </div>
                <div className="flex flex-col gap-0.5 min-w-0">
                  <span
                    className="truncate text-sm font-medium"
                    data-testid="kb-ingestion-history-source-name"
                  >
                    {primaryLabel}
                  </span>
                  {showTypeSubtitle && (
                    <span className="truncate text-xs text-muted-foreground">
                      {typeLabel}
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
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
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default IngestionHistoryPanel;
