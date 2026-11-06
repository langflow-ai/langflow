import { useTranslation } from "react-i18next";
import type { DecisionEvidence } from "./decision-evidence";
import { KNOWN_FAILURE_CATEGORIES } from "./decision-outcome";

const isKnownCategory = (
  category: string,
): category is (typeof KNOWN_FAILURE_CATEGORIES)[number] =>
  (KNOWN_FAILURE_CATEGORIES as readonly string[]).includes(category);

/**
 * The original failure category and the backend's readable diagnostics, or the
 * provider's refusal. Shown as plain text exactly as supplied.
 */
export function DecisionFailureDetails({
  evidence,
}: {
  evidence: DecisionEvidence;
}) {
  const { t } = useTranslation();
  const error = evidence.policy?.error ?? null;
  const refused = evidence.status === "refusal";
  if (!error && !refused) return null;

  if (error) {
    return (
      <div
        className="rounded-md border border-error-foreground/20 bg-error-background/50 p-3"
        data-testid="decision-failure"
      >
        <p className="text-sm font-medium text-error-foreground">
          {isKnownCategory(error.category)
            ? t(`decision.failure.${error.category}`)
            : error.category}
        </p>
        {error.message && (
          <p
            className="mt-1 whitespace-pre-wrap break-words text-sm text-error-foreground/90"
            data-testid="decision-failure-message"
          >
            {error.message}
          </p>
        )}
      </div>
    );
  }

  return (
    <div
      className="rounded-md border border-border bg-muted p-3"
      data-testid="decision-refusal"
    >
      <p className="text-sm font-medium">{t("decision.failure.refusal")}</p>
      <p className="mt-1 whitespace-pre-wrap break-words text-sm text-muted-foreground">
        {evidence.refusal ?? t("decision.refusalNoReason")}
      </p>
    </div>
  );
}

export default DecisionFailureDetails;
