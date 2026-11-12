import type { RunEstimate } from "@/controllers/API/queries/evals/types";
import { type EstimateQueryState, submitDecision } from "../submitDecision";

function estimate(llmCalls: number): RunEstimate {
  return {
    items: 10,
    basis: "model",
    llm_calls: llmCalls,
    judge_calls: llmCalls,
    flow_tokens_low: 0,
    flow_tokens_high: 0,
    judge_tokens_low: 100,
    judge_tokens_high: 200,
    tokens_low: 100,
    tokens_high: 200,
    cost_low: 0.01,
    cost_high: 0.02,
    unpriced_models: [],
    has_agent: false,
  };
}

function query(overrides: Partial<EstimateQueryState>): EstimateQueryState {
  return {
    data: undefined,
    isFetching: false,
    isPlaceholderData: false,
    isError: false,
    ...overrides,
  };
}

describe("submitDecision", () => {
  it("should ask for confirmation when the run calls a model", () => {
    expect(submitDecision(query({ data: estimate(10) }))).toBe("confirm");
  });

  it("should start right away when the run calls no model", () => {
    expect(submitDecision(query({ data: estimate(0) }))).toBe("run");
  });

  it("should hold submit while the estimate is loading", () => {
    expect(submitDecision(query({ isFetching: true }))).toBe("wait");
  });

  it("should hold submit while a free placeholder is shown for a paid change", () => {
    expect(
      submitDecision(
        query({ data: estimate(0), isPlaceholderData: true, isFetching: true }),
      ),
    ).toBe("wait");
  });

  it("should hold submit while a cached free estimate refetches", () => {
    expect(submitDecision(query({ data: estimate(0), isFetching: true }))).toBe(
      "wait",
    );
  });

  it("should still ask for confirmation when the estimate failed", () => {
    expect(submitDecision(query({ isError: true }))).toBe("confirm");
    expect(submitDecision(query({ isError: true, data: estimate(0) }))).toBe(
      "confirm",
    );
  });

  it("should hold submit when there is no estimate at all", () => {
    expect(submitDecision(query({}))).toBe("wait");
  });
});
