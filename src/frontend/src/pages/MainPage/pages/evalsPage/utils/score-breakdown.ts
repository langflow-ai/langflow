import type {
  EvaluationResult,
  ScorerSpec,
} from "@/controllers/API/queries/evals/types";

export interface ScoreTerm {
  name: string;
  weight: number;
  value: number;
}

export type ScoreBreakdown =
  | { kind: "errored" }
  | { kind: "flagged"; checks: string[] }
  | { kind: "undecided"; skipped: string[] }
  | {
      kind: "scored";
      terms: ScoreTerm[];
      skipped: string[];
      average: number;
      threshold: number;
      passed: boolean;
    };

/**
 * Mirrors the server's pass rule: a safety check the judge flagged fails the row; otherwise a
 * weighted mean of the scores that exist, compared with the threshold.
 */
export function scoreBreakdown(
  result: EvaluationResult,
  scorers: ScorerSpec[],
  threshold: number,
): ScoreBreakdown {
  if (result.error) return { kind: "errored" };
  const flagged = Object.values(result.scores).flatMap((entry) =>
    Object.entries(entry?.safety ?? {})
      .filter(([, failed]) => failed)
      .map(([check]) => check),
  );
  if (flagged.length > 0) return { kind: "flagged", checks: flagged };
  const terms: ScoreTerm[] = [];
  const skipped: string[] = [];
  for (const scorer of scorers) {
    const value = result.scores[scorer.name]?.value;
    if (value === null || value === undefined) {
      skipped.push(scorer.name);
    } else {
      terms.push({ name: scorer.name, weight: scorer.weight ?? 1, value });
    }
  }
  const totalWeight = terms.reduce((sum, term) => sum + term.weight, 0);
  if (totalWeight === 0) return { kind: "undecided", skipped };
  const average =
    terms.reduce((sum, term) => sum + term.weight * term.value, 0) /
    totalWeight;
  return {
    kind: "scored",
    terms,
    skipped,
    average,
    threshold,
    passed: average >= threshold,
  };
}

/** "(0.00 + 1.00) / 2", or "(1 × 0.00 + 3 × 1.00) / 4" when the weights differ. */
export function formatFormula(terms: ScoreTerm[]): string {
  const weighted = terms.some((term) => term.weight !== 1);
  const parts = terms.map((term) =>
    weighted
      ? `${term.weight} × ${term.value.toFixed(2)}`
      : term.value.toFixed(2),
  );
  const totalWeight = terms.reduce((sum, term) => sum + term.weight, 0);
  return `(${parts.join(" + ")}) / ${totalWeight}`;
}
