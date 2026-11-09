/**
 * Reads the decision evidence the backend attaches to results, without
 * reinterpreting it. Two producers exist:
 *
 * - the Smart Router in Decision Model mode, whose outputs and "Decision
 *   evidence" log carry the configured policy, what it decided, and the
 *   provider's answer under `result`;
 * - the standalone Decision Model, whose result is the provider's answer plus
 *   the `request` it answered.
 *
 * Any value the backend did not supply stays `null`, so the panel can say it
 * is missing instead of showing it as false or zero.
 */

export type DecisionKind = "choice" | "noul" | "score";

export type DecisionReason =
  | "accepted"
  | "below_minimum_probability"
  | "tied_top_probability"
  | "refusal"
  | "evaluation_error"
  | "configuration_error"
  | "permission_denied";

export interface DecisionCandidate {
  id: string;
  label: string;
  description: string;
}

export interface DecisionFailure {
  category: string;
  message: string;
}

/** What the Smart Router's policy did with the answer. */
export interface DecisionPolicy {
  reason: DecisionReason | null;
  topOutcome: string | null;
  appliedThreshold: number | null;
  minimumProbability: number | null;
  thresholds: Record<string, number>;
  /** The output that received the message; `null` when none did. */
  activatedBranch: string | null;
  errorAction: string | null;
  error: DecisionFailure | null;
}

export interface DecisionEvidence {
  kind: DecisionKind;
  question: string | null;
  provider: string | null;
  model: string | null;
  /** False when the provider did not name the model and the request's is shown. */
  modelReported: boolean;
  /** `null` when the provider never answered, such as after a failure. */
  status: "success" | "refusal" | null;
  candidates: DecisionCandidate[];
  /** Probability per candidate ID, as the provider or router reported it. */
  probabilities: Record<string, number> | null;
  probabilityTrue: number | null;
  score: number | null;
  selectedOption: string | null;
  confidence: number | null;
  refusal: string | null;
  requestId: string | null;
  /** Present for the Smart Router only; a Decision Model applies no policy. */
  policy: DecisionPolicy | null;
}

/** The Smart Router's Else output. */
export const ELSE_BRANCH = "default_result";

/** The log entry the Smart Router writes, also kept when the run stops. */
export const DECISION_EVIDENCE_LOG = "Decision evidence";

const KINDS: readonly DecisionKind[] = ["choice", "noul", "score"];
const REASONS: readonly DecisionReason[] = [
  "accepted",
  "below_minimum_probability",
  "tied_top_probability",
  "refusal",
  "evaluation_error",
  "configuration_error",
  "permission_denied",
];
// Results nest evidence a few levels down (outputs → message → decision);
// the cap keeps a large unrelated payload from being walked in full.
const MAX_DEPTH = 5;
const MAX_VISITS = 500;

type UnknownRecord = Record<string, unknown>;

const isRecord = (value: unknown): value is UnknownRecord =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const text = (value: unknown): string | null =>
  typeof value === "string" && value.trim() !== "" ? value : null;

const finite = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null;

const probability = (value: unknown): number | null => {
  const number = finite(value);
  return number !== null && number >= 0 && number <= 1 ? number : null;
};

// Component code saved before the Boolean -> Noul rename still reports "boolean".
const kindOf = (value: unknown): DecisionKind | null =>
  value === "boolean"
    ? "noul"
    : KINDS.includes(value as DecisionKind)
      ? (value as DecisionKind)
      : null;

const isKind = (value: unknown): boolean => kindOf(value) !== null;

function probabilityMap(value: unknown): Record<string, number> | null {
  if (!isRecord(value)) return null;
  const entries = Object.entries(value).flatMap(([id, raw]) => {
    const number = probability(raw);
    return number === null ? [] : [[id, number] as const];
  });
  return entries.length > 0 ? Object.fromEntries(entries) : null;
}

function candidatesOf(value: unknown): DecisionCandidate[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((row) => {
    if (!isRecord(row)) return [];
    const id = text(row.id);
    if (id === null) return [];
    return [
      {
        id,
        label: text(row.label) ?? id,
        description: text(row.description) ?? "",
      },
    ];
  });
}

function failureOf(value: unknown): DecisionFailure | null {
  if (!isRecord(value)) return null;
  const category = text(value.category);
  if (category === null) return null;
  return { category, message: text(value.message) ?? "" };
}

const isRouterEvidence = (value: UnknownRecord): boolean =>
  isKind(value.kind) && Array.isArray(value.options) && "error_action" in value;

// A Decision Model returns its request with the answer; the router's nested
// `result` has none, so it is never mistaken for a standalone decision.
const isDecisionModelResult = (value: UnknownRecord): boolean =>
  isKind(value.kind) &&
  isRecord(value.request) &&
  typeof value.provider === "string" &&
  typeof value.model === "string" &&
  (value.status === "success" || value.status === "refusal");

type ProviderAnswer = Omit<
  DecisionEvidence,
  "kind" | "question" | "candidates" | "policy"
>;

/** The provider's answer, shared by both producers. */
function answerOf(result: UnknownRecord | null): ProviderAnswer {
  const status = result?.status;
  return {
    provider: text(result?.provider),
    model: text(result?.model),
    modelReported: result?.model_source !== "request",
    status: status === "success" || status === "refusal" ? status : null,
    probabilities: probabilityMap(result?.probabilities),
    probabilityTrue: probability(result?.probability_true),
    score: finite(result?.score),
    selectedOption: text(result?.selected_option),
    confidence: probability(result?.confidence),
    refusal: text(result?.refusal),
    requestId: text(result?.request_id),
  };
}

function fromRouter(evidence: UnknownRecord): DecisionEvidence {
  const result = isRecord(evidence.result) ? evidence.result : null;
  const answer = answerOf(result);
  const reason = REASONS.includes(evidence.reason as DecisionReason)
    ? (evidence.reason as DecisionReason)
    : null;
  return {
    kind: kindOf(evidence.kind) as DecisionKind,
    question: null,
    ...answer,
    // Noul routes on P(yes) and P(no), which the router derives and reports.
    probabilities:
      probabilityMap(evidence.route_probabilities) ?? answer.probabilities,
    candidates: candidatesOf(evidence.options),
    policy: {
      reason,
      topOutcome: text(evidence.top_outcome),
      appliedThreshold: probability(evidence.applied_threshold),
      minimumProbability: probability(evidence.minimum_probability),
      thresholds: probabilityMap(evidence.route_thresholds) ?? {},
      activatedBranch: text(evidence.activated_branch),
      errorAction: text(evidence.error_action),
      error: failureOf(evidence.error),
    },
  };
}

function fromDecisionModel(result: UnknownRecord): DecisionEvidence {
  const request = result.request as UnknownRecord;
  const kind = kindOf(result.kind) as DecisionKind;
  return {
    kind,
    question: text(request.question),
    ...answerOf(result),
    candidates: candidatesOf(
      kind === "score" ? request.levels : request.options,
    ),
    policy: null,
  };
}

function parse(value: UnknownRecord): DecisionEvidence | null {
  if (isRouterEvidence(value)) return fromRouter(value);
  if (isDecisionModelResult(value)) return fromDecisionModel(value);
  return null;
}

/**
 * The first decision evidence found in a component result, log list or trace
 * span output, searched breadth first so the outermost evidence wins.
 */
export function findDecisionEvidence(value: unknown): DecisionEvidence | null {
  let queue: unknown[] = [value];
  let visits = 0;
  for (let depth = 0; depth <= MAX_DEPTH && queue.length > 0; depth++) {
    const next: unknown[] = [];
    for (const item of queue) {
      if (++visits > MAX_VISITS) return null;
      if (Array.isArray(item)) {
        next.push(...item);
        continue;
      }
      if (!isRecord(item)) continue;
      const evidence = parse(item);
      if (evidence) return evidence;
      next.push(...Object.values(item));
    }
    queue = next;
  }
  return null;
}
