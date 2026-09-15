import type { Ref } from "react";
import { useTranslation } from "react-i18next";
import type { SourcedReport } from "@/controllers/API/queries/folders/use-project-reports";
import { sourceURL } from "./report-markdown";

export function ReportEvidence({
  report,
  sourceIds,
  selectedId,
  onSelect,
  selectRef,
}: {
  report: SourcedReport;
  sourceIds: string[];
  selectedId: string;
  onSelect: (id: string) => void;
  selectRef: Ref<HTMLSelectElement>;
}) {
  const { t, i18n } = useTranslation();
  const source = report.sources.find((item) => item.id === selectedId);
  const url = source && sourceURL(source.uri);
  const uses = report.source_uses.filter((use) => use.source_id === selectedId);
  return (
    <aside
      aria-label={t("reports.evidence")}
      className="flex min-h-0 min-w-0 flex-col border-l border-border bg-muted/20"
    >
      <div className="space-y-3 border-b border-border p-5">
        <label
          className="block text-sm font-semibold"
          htmlFor="report-evidence-source"
        >
          {t("reports.evidence")}
        </label>
        {sourceIds.length > 0 ? (
          <select
            id="report-evidence-source"
            ref={selectRef}
            value={selectedId}
            onChange={(event) => onSelect(event.target.value)}
            className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
          >
            {sourceIds.map((id, index) => (
              <option key={id} value={id}>
                {index + 1}.{" "}
                {report.sources.find((item) => item.id === id)?.title ||
                  t("reports.missingSource")}
              </option>
            ))}
          </select>
        ) : (
          <p className="text-sm text-muted-foreground">
            {t("reports.noSources")}
          </p>
        )}
        {source && (
          <>
            <p className="break-words text-xs text-muted-foreground">
              {url ? (
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline underline-offset-4 hover:text-foreground"
                >
                  {source.uri}
                </a>
              ) : (
                source.uri
              )}
            </p>
            <p className="text-xs text-muted-foreground">
              {t("reports.captured", {
                date: new Date(source.captured_at).toLocaleString(
                  i18n.language,
                ),
              })}
            </p>
          </>
        )}
      </div>
      {source?.availability === "available" ? (
        <div className="flex min-h-0 flex-1 flex-col gap-3 p-5">
          <p className="text-xs font-medium text-muted-foreground">
            {t("reports.originalText")}
          </p>
          <pre
            key={source.id}
            data-testid="report-source-content"
            tabIndex={0}
            aria-label={t("reports.originalText")}
            className="min-h-0 flex-1 overflow-y-auto whitespace-pre-wrap break-words font-sans text-sm leading-relaxed focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
          >
            {source.content}
          </pre>
        </div>
      ) : (
        sourceIds.length > 0 && (
          <div role="status" className="space-y-2 p-5 text-sm">
            <p className="font-medium">
              {t(
                source ? "reports.unavailableSource" : "reports.missingSource",
              )}
            </p>
            <p className="break-words text-muted-foreground">
              {source?.unavailable_reason || t("reports.missingSourceHelp")}
            </p>
          </div>
        )
      )}
      {uses.length > 0 && (
        <details className="max-h-40 shrink-0 overflow-auto border-t border-border p-5 text-xs">
          <summary className="cursor-pointer font-medium">
            {t("reports.collectedByTool")}
          </summary>
          <ul className="mt-3 space-y-2">
            {uses.map((use) => (
              <li
                key={`${use.tool_call_id}:${use.source_id}`}
                className="break-all"
              >
                {use.tool_name}
                <span className="block font-mono text-muted-foreground">
                  {use.tool_call_id}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </aside>
  );
}
