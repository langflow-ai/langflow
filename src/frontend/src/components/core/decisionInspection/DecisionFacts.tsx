import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { DecisionEvidence, DecisionKind } from "./decision-evidence";
import type { DecisionFormatters } from "./decision-outcome";

// The Decision Type options as the node shows them; component options aren't translated.
const KIND_LABEL: Record<DecisionKind, string> = {
  choice: "Choice",
  noul: "Noul",
  score: "Score",
};

interface DecisionFactsProps {
  evidence: DecisionEvidence;
  format: DecisionFormatters;
}

function Fact({
  label,
  testId,
  children,
}: {
  label: string;
  testId: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="break-words text-sm" data-testid={testId}>
        {children}
      </dd>
    </div>
  );
}

/**
 * Who answered and the numbers the provider reported. A rating, a probability
 * and the provider's confidence are separate facts and never stand in for one
 * another; a value the provider did not send reads "Not reported".
 */
export function DecisionFacts({ evidence, format }: DecisionFactsProps) {
  const { t } = useTranslation();
  const missing = t("decision.notReported");
  const show = (value: number | null, as: "percent" | "number") =>
    value === null ? missing : format[as](value);
  const policy = evidence.policy;
  const lastLevel = Math.max(evidence.candidates.length - 1, 0);

  return (
    <dl
      className="grid grid-cols-1 gap-3 sm:grid-cols-2"
      data-testid="decision-facts"
    >
      <Fact label={t("decision.model")} testId="decision-model">
        {evidence.provider && evidence.model
          ? t("decision.providerModel", {
              provider: evidence.provider,
              model: evidence.model,
            })
          : missing}
        {evidence.model && !evidence.modelReported && (
          <span className="block text-xs text-muted-foreground">
            {t("decision.modelAsRequested")}
          </span>
        )}
      </Fact>
      <Fact label={t("decision.type")} testId="decision-type">
        {KIND_LABEL[evidence.kind]}
      </Fact>
      {evidence.question && (
        <Fact label={t("decision.question")} testId="decision-question">
          {evidence.question}
        </Fact>
      )}
      {evidence.kind === "noul" && (
        <Fact
          label={t("decision.probabilityTrue")}
          testId="decision-probability-true"
        >
          {show(evidence.probabilityTrue, "percent")}
        </Fact>
      )}
      {evidence.kind === "score" && (
        <Fact label={t("decision.score")} testId="decision-score">
          {evidence.score === null
            ? missing
            : t("decision.scoreOnScale", {
                score: format.number(evidence.score),
                max: format.number(lastLevel),
              })}
        </Fact>
      )}
      <Fact label={t("decision.confidence")} testId="decision-confidence">
        {show(evidence.confidence, "percent")}
      </Fact>
      {policy && evidence.kind !== "score" && (
        <Fact
          label={t("decision.minimumProbability")}
          testId="decision-minimum-probability"
        >
          {show(policy.minimumProbability, "percent")}
        </Fact>
      )}
      {policy?.errorAction && (
        <Fact label={t("decision.errorAction")} testId="decision-error-action">
          {/* As the node shows it, like the Decision Type. */}
          {policy.errorAction}
        </Fact>
      )}
      {evidence.requestId && (
        <Fact label={t("decision.requestId")} testId="decision-request-id">
          <span className="font-mono text-xs">{evidence.requestId}</span>
        </Fact>
      )}
    </dl>
  );
}

export default DecisionFacts;
