import type { ScorerType } from "@/controllers/API/queries/evals/types";
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
});
