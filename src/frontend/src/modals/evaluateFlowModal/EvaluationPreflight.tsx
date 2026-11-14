import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type {
  FlowCheckIssue,
  FlowCheckReport,
} from "@/controllers/API/queries/evals/types";
import { cn } from "@/utils/utils";

function IssueItem({
  issue,
  blocking,
}: {
  issue: FlowCheckIssue;
  blocking: boolean;
}) {
  const { t } = useTranslation();
  return (
    <li className="flex gap-2 text-sm">
      <ForwardedIconComponent
        name={blocking ? "CircleX" : "TriangleAlert"}
        aria-hidden="true"
        className={cn(
          "mt-0.5 h-4 w-4 shrink-0",
          blocking ? "text-destructive" : "text-accent-amber-foreground",
        )}
      />
      <span>
        {t(`evals.checks.${issue.code}`, { defaultValue: issue.message })}
        {issue.components.length > 0 && (
          <span className="text-muted-foreground">
            {" "}
            ({issue.components.join(", ")})
          </span>
        )}
      </span>
    </li>
  );
}

/** Blocking problems first (announced), then warnings; renders nothing when the flow is clean. */
export default function EvaluationPreflight({
  report,
  failed = false,
}: {
  report?: FlowCheckReport;
  /** The check itself could not run, so Submit stays disabled: say why. */
  failed?: boolean;
}) {
  const { t } = useTranslation();
  if (failed) {
    return (
      <p
        role="alert"
        className="rounded-lg border border-destructive/40 px-4 py-3 text-sm"
        data-testid="evaluate-check-error"
      >
        {t("evals.evaluate.checkError")}
      </p>
    );
  }
  if (
    !report ||
    (report.blocking.length === 0 && report.warnings.length === 0)
  ) {
    return null;
  }
  return (
    <div className="flex flex-col gap-3">
      {report.blocking.length > 0 && (
        <div
          role="alert"
          className="rounded-lg border border-destructive/40 px-4 py-3"
        >
          <ul className="flex flex-col gap-2" data-testid="evaluate-blocking">
            {report.blocking.map((issue) => (
              <IssueItem key={issue.code} issue={issue} blocking />
            ))}
          </ul>
        </div>
      )}
      {report.warnings.length > 0 && (
        <div className="rounded-lg border border-accent-amber-foreground/40 px-4 py-3">
          <ul className="flex flex-col gap-2" data-testid="evaluate-warnings">
            {report.warnings.map((issue) => (
              <IssueItem key={issue.code} issue={issue} blocking={false} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
