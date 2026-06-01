import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { useGetIngestionRun } from "@/controllers/API/queries/knowledge-bases/use-get-ingestion-run";

interface IngestionRunDetailModalProps {
  kbName: string;
  runId: string;
  onClose: () => void;
}

const ITEM_STATUS_STYLES: Record<string, string> = {
  succeeded: "text-accent-emerald-foreground",
  failed: "text-accent-red-foreground",
  skipped: "text-muted-foreground",
};

const ITEM_STATUS_ICON: Record<string, string> = {
  succeeded: "CircleCheck",
  failed: "CircleAlert",
  skipped: "CircleMinus",
};

const IngestionRunDetailModal = ({
  kbName,
  runId,
  onClose,
}: IngestionRunDetailModalProps) => {
  const { t } = useTranslation();
  const { data, isLoading, isError } = useGetIngestionRun({
    kb_name: kbName,
    run_id: runId,
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="flex max-h-[80vh] w-full max-w-2xl flex-col overflow-hidden rounded-lg border border-border bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <div className="text-sm font-semibold">
              {t("knowledge.ingestionRunDetail")}
            </div>
            {data && (
              <div className="text-xs text-muted-foreground">
                {kbName} · {data.source_type} ·{" "}
                {new Date(data.started_at).toLocaleString()}
              </div>
            )}
          </div>
          <Button variant="ghost" size="iconSm" onClick={onClose}>
            <ForwardedIconComponent name="X" className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-3">
          {isLoading && (
            <div className="text-sm text-muted-foreground">
              {t("knowledge.loadingRun")}
            </div>
          )}
          {isError && (
            <div className="text-sm text-destructive">
              {t("knowledge.unableToLoadRunDetail")}
            </div>
          )}

          {data && (
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-4 gap-3">
                <Metric
                  label={t("knowledge.metricSucceeded")}
                  value={data.succeeded}
                  tone="success"
                />
                <Metric
                  label={t("knowledge.metricFailed")}
                  value={data.failed}
                  tone="error"
                />
                <Metric
                  label={t("knowledge.metricSkipped")}
                  value={data.skipped}
                  tone="muted"
                />
                <Metric
                  label={t("knowledge.metricChunks")}
                  value={data.chunks_created}
                />
              </div>

              {data.error_message && (
                <div className="rounded-md border border-error-red-border bg-error-red p-3 text-xs text-accent-red-foreground">
                  <span className="font-medium">
                    {t("knowledge.errorLabel")}
                  </span>{" "}
                  {data.error_message}
                </div>
              )}

              <div className="grid grid-cols-1 gap-2 rounded-md border border-border bg-card p-3 text-xs sm:grid-cols-2">
                <IdField label={t("knowledge.runId")} value={data.id} />
                <IdField label={t("knowledge.jobId")} value={data.job_id} />
              </div>

              <div>
                <div className="mb-2 text-xs font-medium text-muted-foreground">
                  Files ({data.items.length})
                </div>
                <div className="flex flex-col divide-y divide-border rounded-md border border-border">
                  {data.items.map((item) => {
                    const toneClass =
                      ITEM_STATUS_STYLES[item.status] ??
                      "text-muted-foreground";
                    const iconName = ITEM_STATUS_ICON[item.status] ?? "Circle";
                    return (
                      <div
                        key={item.item_id}
                        className="flex flex-col gap-1 px-3 py-2 text-xs"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="flex items-center gap-2 truncate">
                            <ForwardedIconComponent
                              name={iconName}
                              className={`h-3 w-3 shrink-0 ${toneClass}`}
                            />
                            <span className="truncate font-medium">
                              {item.display_name}
                            </span>
                          </span>
                          <span className="shrink-0 text-muted-foreground">
                            {item.chunks_created} chunks
                          </span>
                        </div>
                        {item.error_message && (
                          <div className="rounded-sm bg-error-red px-2 py-1 text-accent-red-foreground">
                            {item.error_message}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

interface MetricProps {
  label: string;
  value: number;
  tone?: "success" | "error" | "muted";
}

function Metric({ label, value, tone }: MetricProps) {
  const toneClass =
    tone === "success"
      ? "text-accent-emerald-foreground"
      : tone === "error"
        ? "text-accent-red-foreground"
        : tone === "muted"
          ? "text-muted-foreground"
          : "text-foreground";
  return (
    <div className="flex flex-col gap-1 rounded-md border border-border bg-card p-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`text-lg font-semibold ${toneClass}`}>{value}</div>
    </div>
  );
}

interface IdFieldProps {
  label: string;
  value: string | null | undefined;
}

function IdField({ label, value }: IdFieldProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div
        className="truncate font-mono text-xs text-foreground"
        title={value ?? undefined}
        data-testid={`run-detail-${label.toLowerCase().replace(/\s+/g, "-")}`}
      >
        {value ?? "—"}
      </div>
    </div>
  );
}

export default IngestionRunDetailModal;
