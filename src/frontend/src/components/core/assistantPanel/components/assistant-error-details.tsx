/**
 * Collapsed "Error details" expander rendered under an assistant error
 * message when the SSE error event carried the additive ``detail`` object.
 * Uses a native <details> element so it is keyboard-operable and needs no
 * open/close state; every label goes through i18n.
 */

import { ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { AgenticErrorDetail } from "@/controllers/API/queries/agentic";

interface AssistantErrorDetailsProps {
  detail: AgenticErrorDetail;
}

function DetailRow({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <div className="flex gap-2 text-xs">
      <span className="shrink-0 font-medium text-muted-foreground">
        {label}:
      </span>
      <span className="break-words text-foreground">{value}</span>
    </div>
  );
}

export function AssistantErrorDetails({ detail }: AssistantErrorDetailsProps) {
  const { t } = useTranslation();
  const hasAnyField = Boolean(
    detail.step ||
      detail.component_id ||
      detail.tool ||
      detail.raw_cause ||
      detail.recommendation,
  );
  if (!hasAnyField) return null;

  return (
    <details
      className="group mt-1 rounded-md border border-border/60 px-2 py-1"
      data-testid="assistant-error-details"
    >
      <summary className="flex cursor-pointer list-none items-center gap-1 text-xs text-muted-foreground [&::-webkit-details-marker]:hidden">
        <ChevronRight
          className="h-3 w-3 transition-transform group-open:rotate-90"
          aria-hidden="true"
        />
        {t("assistant.errorDetails.title")}
      </summary>
      <div className="mt-1.5 flex flex-col gap-1 pl-4">
        <DetailRow
          label={t("assistant.errorDetails.step")}
          value={detail.step}
        />
        <DetailRow
          label={t("assistant.errorDetails.component")}
          value={detail.component_id}
        />
        <DetailRow
          label={t("assistant.errorDetails.tool")}
          value={detail.tool}
        />
        <DetailRow
          label={t("assistant.errorDetails.recommendation")}
          value={detail.recommendation}
        />
        {detail.raw_cause && (
          <div className="flex flex-col gap-0.5 text-xs">
            <span className="font-medium text-muted-foreground">
              {t("assistant.errorDetails.rawError")}:
            </span>
            <pre
              className="max-h-40 overflow-auto whitespace-pre-wrap break-words rounded bg-muted px-1.5 py-1 font-mono text-[11px] text-muted-foreground"
              data-testid="assistant-error-details-raw-cause"
            >
              {detail.raw_cause}
            </pre>
          </div>
        )}
      </div>
    </details>
  );
}
