import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { FlowCheckReport } from "@/controllers/API/queries/evals/types";

/** The good news of the flow check: it can run, which answer is scored, which models can be swapped. */
export default function FlowReadiness({
  report,
  outputName,
  models,
}: {
  report: FlowCheckReport;
  outputName?: string;
  models: number;
}) {
  const { t } = useTranslation();
  if (report.blocking.length > 0) return null;
  return (
    <div
      className="flex items-start gap-3 rounded-lg border px-4 py-3 text-sm"
      data-testid="evaluate-ready"
    >
      <ForwardedIconComponent
        name="CircleCheck"
        aria-hidden="true"
        className="mt-0.5 h-4 w-4 shrink-0 text-accent-emerald-foreground"
      />
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="font-medium">{t("evals.evaluate.ready")}</span>
        {outputName && (
          <span className="text-muted-foreground">
            {t("evals.evaluate.readyOutput", { output: outputName })}
          </span>
        )}
        {models > 0 && (
          <span className="text-muted-foreground">
            {t("evals.evaluate.readyModels", { count: models })}
          </span>
        )}
      </div>
    </div>
  );
}
