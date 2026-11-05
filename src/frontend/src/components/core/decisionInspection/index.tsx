import { useId } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/utils/utils";
import DecisionDistribution from "./DecisionDistribution";
import DecisionFacts from "./DecisionFacts";
import DecisionFailureDetails from "./DecisionFailureDetails";
import DecisionSummary from "./DecisionSummary";
import type { DecisionEvidence } from "./decision-evidence";
import { describeDecisionOutcome } from "./decision-outcome";
import { useDecisionFormatters } from "./use-decision-formatters";

interface DecisionInspectionProps {
  evidence: DecisionEvidence;
  className?: string;
}

/**
 * Read-only view of a decision: the model's answer and the policy that chose a
 * branch, from the evidence the backend recorded. It never runs anything.
 */
export function DecisionInspection({
  evidence,
  className,
}: DecisionInspectionProps) {
  const { t } = useTranslation();
  const format = useDecisionFormatters();
  const titleId = useId();
  const outcome = describeDecisionOutcome(evidence, format);
  return (
    <section
      aria-labelledby={titleId}
      className={cn(
        "flex flex-col gap-4 rounded-md border border-border bg-background p-4",
        className,
      )}
      data-testid="decision-inspection"
    >
      <h4 id={titleId} className="text-sm font-semibold">
        {t("decision.title")}
      </h4>
      <DecisionSummary outcome={outcome} />
      <DecisionFailureDetails evidence={evidence} />
      <DecisionDistribution evidence={evidence} format={format} />
      <DecisionFacts evidence={evidence} format={format} />
    </section>
  );
}

export default DecisionInspection;
