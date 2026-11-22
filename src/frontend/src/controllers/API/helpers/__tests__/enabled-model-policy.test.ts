import type { EnabledModelsResponse } from "@/controllers/API/queries/models/use-get-enabled-models";
import {
  getEnabledModelsForType,
  isModelEnabledForType,
} from "../enabled-model-policy";

// gpt-6-luna is both an OpenAI chat model and a decision model.
const data: EnabledModelsResponse = {
  enabled_models: {
    OpenAI: { "gpt-6-luna": true },
    Legacy: { "jev-latest": true },
  },
  enabled_models_by_type: {
    OpenAI: {
      llm: { "gpt-6-luna": true },
      decision: { "gpt-6-luna": false },
    },
    TypeSafe: { decision: { "jev-latest": true } },
  },
};

describe("isModelEnabledForType", () => {
  it("keeps same-name models of different kinds apart", () => {
    expect(isModelEnabledForType(data, "OpenAI", "gpt-6-luna", "llm")).toBe(
      true,
    );
    expect(
      isModelEnabledForType(data, "OpenAI", "gpt-6-luna", "decision"),
    ).toBe(false);
  });

  it("reads a decision model from the typed map", () => {
    expect(
      isModelEnabledForType(data, "TypeSafe", "jev-latest", "decision"),
    ).toBe(true);
  });

  it("never falls back to the untyped map for a decision model", () => {
    expect(
      isModelEnabledForType(data, "Legacy", "jev-latest", "decision"),
    ).toBe(false);
  });

  it("still falls back to the untyped map for language models", () => {
    expect(isModelEnabledForType(data, "Legacy", "jev-latest", "llm")).toBe(
      true,
    );
  });
});

describe("getEnabledModelsForType", () => {
  it("lists decision models only from typed maps", () => {
    expect(getEnabledModelsForType(data, "decision")).toEqual({
      OpenAI: { "gpt-6-luna": false },
      Legacy: {},
      TypeSafe: { "jev-latest": true },
    });
  });

  it("keeps the untyped fallback for language models", () => {
    expect(getEnabledModelsForType(data, "llm")).toEqual({
      OpenAI: { "gpt-6-luna": true },
      Legacy: { "jev-latest": true },
      TypeSafe: {},
    });
  });
});
