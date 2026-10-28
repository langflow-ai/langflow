import type {
  EvaluationResult,
  ScorerSpec,
} from "@/controllers/API/queries/evals/types";
import { formatFormula, scoreBreakdown } from "../utils/score-breakdown";

const SCORERS: ScorerSpec[] = [
  { type: "exact_match", name: "exact_match" },
  { type: "contains", name: "contains" },
  { type: "similarity", name: "similarity" },
  { type: "llm_judge", name: "llm_judge" },
];

function result(
  values: Record<string, number | null>,
  error: string | null = null,
): EvaluationResult {
  return {
    id: "r",
    position: 0,
    input: "q",
    expected_output: "q",
    actual_output: "a",
    output_truncated: false,
    error,
    scores: Object.fromEntries(
      Object.entries(values).map(([name, value]) => [name, { value }]),
    ),
    passed: null,
    duration_ms: 1,
    tokens_flow: null,
    tokens_judge: null,
    cost_flow: null,
    cost_judge: null,
    trace_id: null,
  };
}

describe("scoreBreakdown", () => {
  it("should average every score and fail below the threshold", () => {
    const breakdown = scoreBreakdown(
      result({ exact_match: 0, contains: 1, similarity: 0.07, llm_judge: 0 }),
      SCORERS,
      0.5,
    );
    expect(breakdown.kind).toBe("scored");
    if (breakdown.kind !== "scored") return;
    expect(breakdown.average).toBeCloseTo(0.2675);
    expect(breakdown.passed).toBe(false);
    expect(formatFormula(breakdown.terms)).toBe(
      "(0.00 + 1.00 + 0.07 + 0.00) / 4",
    );
  });

  it("should leave out a scorer without a score", () => {
    const breakdown = scoreBreakdown(
      result({
        exact_match: 0,
        contains: 1,
        similarity: 0.09,
        llm_judge: null,
      }),
      SCORERS,
      0.5,
    );
    if (breakdown.kind !== "scored") throw new Error(breakdown.kind);
    expect(breakdown.skipped).toEqual(["llm_judge"]);
    expect(breakdown.average).toBeCloseTo(0.3633, 3);
  });

  it("should weigh scores and pass at the threshold", () => {
    const weighted: ScorerSpec[] = [
      { type: "exact_match", name: "exact_match", weight: 1 },
      { type: "llm_judge", name: "llm_judge", weight: 3 },
    ];
    const breakdown = scoreBreakdown(
      result({ exact_match: 0, llm_judge: 1 }),
      weighted,
      0.75,
    );
    if (breakdown.kind !== "scored") throw new Error(breakdown.kind);
    expect(breakdown.passed).toBe(true);
    expect(formatFormula(breakdown.terms)).toBe("(1 × 0.00 + 3 × 1.00) / 4");
  });

  it("should fail an errored row whatever the scores", () => {
    expect(
      scoreBreakdown(result({ contains: 1 }, "boom"), SCORERS, 0.5),
    ).toEqual({ kind: "errored" });
  });

  it("should leave a row without any score undecided", () => {
    const breakdown = scoreBreakdown(result({}), SCORERS, 0.5);
    expect(breakdown.kind).toBe("undecided");
  });
});
