import type { ScorerType } from "@/controllers/API/queries/evals/types";
import {
  isReasoningModel,
  parseJudgeMaxTokens,
  parseJudgeRunMaxTokens,
} from "../judgeLimits";
import { buildScorers } from "../useEvaluateFlowForm";

const JUDGE = [
  {
    name: "gpt-4o-mini",
    provider: "OpenAI",
    icon: "OpenAI",
    metadata: { cost_per_million_in: 0.15 },
  },
];

describe("buildScorers", () => {
  it("should keep the selected text scorers in a stable order", () => {
    const selected = new Set<ScorerType>(["similarity", "exact_match"]);
    expect(buildScorers(selected, [], "")).toEqual([
      { type: "exact_match", name: "exact_match" },
      { type: "similarity", name: "similarity" },
    ]);
  });

  it("should add the judge with its model and trimmed rubric", () => {
    const scorers = buildScorers(new Set(["llm_judge"]), JUDGE, "  be strict ");
    expect(scorers).toEqual([
      {
        type: "llm_judge",
        name: "llm_judge",
        config: {
          model: [JUDGE[0]],
          rubric: "be strict",
          max_output_tokens: 600,
          max_run_output_tokens: 8192,
          stop_on_output_limit: true,
        },
      },
    ]);
  });

  it("should leave the judge out until a model is chosen", () => {
    expect(buildScorers(new Set(["llm_judge"]), [], "rubric")).toEqual([]);
  });

  it("should omit a blank rubric", () => {
    const [judge] = buildScorers(new Set(["llm_judge"]), JUDGE, "   ");
    expect(judge.config?.rubric).toBeUndefined();
  });

  it("should send the judge's output budget and stop choice", () => {
    const [judge] = buildScorers(new Set(["llm_judge"]), JUDGE, "", {
      maxOutputTokens: "2048",
      maxRunOutputTokens: "50000",
      stopOnOutputLimit: false,
    });
    expect(judge.config?.max_output_tokens).toBe(2048);
    expect(judge.config?.max_run_output_tokens).toBe(50000);
    expect(judge.config?.stop_on_output_limit).toBe(false);
  });
});

describe("buildScorers with safety checks", () => {
  it("should add the chosen checks to the judge config", () => {
    const [judge] = buildScorers(
      new Set<ScorerType>(["llm_judge"]),
      JUDGE,
      "",
      undefined,
      ["pii_exposure", "jailbreak"],
    );
    expect(judge.config?.safety_checks).toEqual(["pii_exposure", "jailbreak"]);
  });

  it("should leave safety_checks out when none is chosen", () => {
    const [judge] = buildScorers(new Set<ScorerType>(["llm_judge"]), JUDGE, "");
    expect(judge.config).not.toHaveProperty("safety_checks");
  });
});

describe("parseJudgeMaxTokens", () => {
  it("should accept whole numbers in range only", () => {
    expect(parseJudgeMaxTokens("300")).toBe(300);
    expect(parseJudgeMaxTokens(" 2048 ")).toBe(2048);
    for (const bad of ["", "0", "-5", "1.5", "abc", "40000"]) {
      expect(parseJudgeMaxTokens(bad)).toBeNull();
    }
  });

  it("should need the run budget to cover at least one row", () => {
    expect(parseJudgeRunMaxTokens("8192", 600)).toBe(8192);
    expect(parseJudgeRunMaxTokens("500", 600)).toBeNull();
    expect(parseJudgeRunMaxTokens("x", 600)).toBeNull();
  });

  it("should spot a reasoning model from its catalog metadata", () => {
    expect(isReasoningModel({ reasoning: true })).toBe(true);
    expect(isReasoningModel({ reasoning: false })).toBe(false);
    expect(isReasoningModel(undefined)).toBe(false);
  });
});
