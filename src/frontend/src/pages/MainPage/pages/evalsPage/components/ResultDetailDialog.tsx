import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { EvaluationResult } from "@/controllers/API/queries/evals/types";
import BaseModal from "@/modals/baseModal";
import {
  formatDuration,
  formatScore,
  formatTokenCount,
  formatUsd,
} from "../utils/format";
import PassedBadge from "./PassedBadge";

function TextBlock({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <div className="max-h-48 overflow-y-auto whitespace-pre-wrap break-words rounded-lg border bg-muted/40 px-3 py-2 text-sm">
        {children}
      </div>
    </div>
  );
}

interface ResultDetailDialogProps {
  result: EvaluationResult | null;
  scorerNames: string[];
  onClose: () => void;
}

/** The full row: long text is never cut here, and the judge's reason is readable. */
export default function ResultDetailDialog({
  result,
  scorerNames,
  onClose,
}: ResultDetailDialogProps) {
  const { t } = useTranslation();
  if (!result) return null;
  const totalTokens = (result.tokens_flow ?? 0) + (result.tokens_judge ?? 0);
  const cost =
    result.cost_flow === null && result.cost_judge === null
      ? null
      : (result.cost_flow ?? 0) + (result.cost_judge ?? 0);
  return (
    <BaseModal
      open
      setOpen={(open) => !open && onClose()}
      size="smaller-h-full"
    >
      <BaseModal.Header
        description={t("evals.results.detailDescription", {
          row: result.position + 1,
        })}
      >
        <ForwardedIconComponent name="ScanText" className="mr-2 h-4 w-4" />
        {t("evals.results.detailTitle", { row: result.position + 1 })}
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="flex flex-col gap-4 px-1 pb-1">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <PassedBadge passed={result.passed} />
            <span>{formatDuration(result.duration_ms)}</span>
            <span>
              {t("evals.results.tokensValue", {
                value: formatTokenCount(totalTokens || null),
              })}
            </span>
            <span>{formatUsd(cost)}</span>
          </div>
          <TextBlock label={t("evals.items.input")}>{result.input}</TextBlock>
          <TextBlock label={t("evals.items.expected")}>
            {result.expected_output ?? "—"}
          </TextBlock>
          <TextBlock label={t("evals.results.actual")}>
            {result.error ? (
              <span className="text-destructive">{result.error}</span>
            ) : (
              result.actual_output
            )}
            {result.output_truncated && (
              <span className="mt-2 block text-xs text-muted-foreground">
                {t("evals.results.truncated")}
              </span>
            )}
          </TextBlock>
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">
              {t("evals.results.scores")}
            </span>
            <ul className="divide-y rounded-lg border">
              {scorerNames.map((name) => {
                const entry = result.scores[name];
                return (
                  <li key={name} className="flex flex-col gap-0.5 px-3 py-2">
                    <div className="flex items-center justify-between text-sm">
                      <span>{name}</span>
                      <span className="font-medium tabular-nums">
                        {formatScore(entry?.value)}
                      </span>
                    </div>
                    {entry?.comment && (
                      <span className="text-xs text-muted-foreground">
                        {entry.comment}
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
