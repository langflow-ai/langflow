import {
  type DecisionEvidence,
  type DecisionReason,
  ELSE_BRANCH,
} from "./decision-evidence";

/**
 * How a decision ended. A Decision Model only answers; the Smart Router's
 * policy accepts an answer or not. Uncertainty is a valid answer the policy sent to Else;
 * a refusal or an error is an operational outcome, kept apart so the two are
 * never read as the same thing.
 */
export type DecisionTone =
  | "answered"
  | "accepted"
  | "uncertain"
  | "refused"
  | "error";

export type DecisionBranch =
  | { kind: "route"; label: string }
  | { kind: "else" }
  | { kind: "stopped" };

export interface DecisionOutcome {
  tone: DecisionTone;
  /** `null` for a Decision Model, which routes nothing. */
  branch: DecisionBranch | null;
  /** A factual policy statement; never the model's reasoning. */
  reasonKey: string;
  reasonParams: Record<string, string | number>;
}

export interface DecisionFormatters {
  percent: (value: number) => string;
  number: (value: number) => string;
}

const TONE_BY_REASON: Record<DecisionReason, DecisionTone> = {
  accepted: "accepted",
  below_minimum_probability: "uncertain",
  tied_top_probability: "uncertain",
  refusal: "refused",
  evaluation_error: "error",
  configuration_error: "error",
  permission_denied: "error",
};

/** Failure categories the backend reports, each with its own label. */
export const KNOWN_FAILURE_CATEGORIES = [
  "timeout",
  "transport",
  "http_error",
  "input_too_large",
  "invalid_response",
  "refusal",
  "configuration_error",
  "permission_denied",
] as const;

export function labelOf(evidence: DecisionEvidence, id: string | null): string {
  if (id === null) return "";
  return evidence.candidates.find((c) => c.id === id)?.label ?? id;
}

function branchOf(evidence: DecisionEvidence): DecisionBranch {
  const branch = evidence.policy?.activatedBranch ?? null;
  if (branch === null) return { kind: "stopped" };
  if (branch === ELSE_BRANCH) return { kind: "else" };
  return { kind: "route", label: labelOf(evidence, branch) };
}

function routerReason(
  evidence: DecisionEvidence,
  format: DecisionFormatters,
): Pick<DecisionOutcome, "reasonKey" | "reasonParams"> {
  const policy = evidence.policy!;
  const top = policy.topOutcome;
  const topProbability =
    top !== null ? (evidence.probabilities?.[top] ?? null) : null;
  switch (policy.reason) {
    case "accepted":
      if (evidence.kind === "score" && evidence.score !== null) {
        return {
          reasonKey: "decision.reason.scoreLevel",
          reasonParams: {
            score: format.number(evidence.score),
            level: labelOf(evidence, policy.activatedBranch),
          },
        };
      }
      if (topProbability !== null && policy.appliedThreshold !== null) {
        return {
          reasonKey: "decision.reason.accepted",
          reasonParams: {
            option: labelOf(evidence, top),
            probability: format.percent(topProbability),
            threshold: format.percent(policy.appliedThreshold),
          },
        };
      }
      return { reasonKey: "decision.reason.acceptedPlain", reasonParams: {} };
    case "below_minimum_probability":
      if (topProbability !== null && policy.appliedThreshold !== null) {
        return {
          reasonKey: "decision.reason.belowThreshold",
          reasonParams: {
            option: labelOf(evidence, top),
            probability: format.percent(topProbability),
            threshold: format.percent(policy.appliedThreshold),
          },
        };
      }
      return {
        reasonKey: "decision.reason.belowThresholdPlain",
        reasonParams: {},
      };
    case "tied_top_probability": {
      const values = Object.values(evidence.probabilities ?? {});
      return values.length > 0
        ? {
            reasonKey: "decision.reason.tied",
            reasonParams: { probability: format.percent(Math.max(...values)) },
          }
        : { reasonKey: "decision.reason.tiedPlain", reasonParams: {} };
    }
    case "refusal":
      return { reasonKey: "decision.reason.refusal", reasonParams: {} };
    case "evaluation_error":
      return { reasonKey: "decision.reason.evaluationError", reasonParams: {} };
    case "configuration_error":
      return {
        reasonKey: "decision.reason.configurationError",
        reasonParams: {},
      };
    case "permission_denied":
      return {
        reasonKey: "decision.reason.permissionDenied",
        reasonParams: {},
      };
    default:
      return { reasonKey: "decision.reason.unknown", reasonParams: {} };
  }
}

export function describeDecisionOutcome(
  evidence: DecisionEvidence,
  format: DecisionFormatters,
): DecisionOutcome {
  if (evidence.policy === null) {
    const refused = evidence.status === "refusal";
    return {
      tone: refused ? "refused" : "answered",
      branch: null,
      reasonKey: refused
        ? "decision.reason.refusal"
        : "decision.reason.answered",
      reasonParams: {},
    };
  }
  const reason = evidence.policy.reason;
  // An evidence record without a reason was cut short by an error.
  const tone = reason === null ? "error" : TONE_BY_REASON[reason];
  return {
    tone,
    branch: branchOf(evidence),
    ...routerReason(evidence, format),
  };
}
