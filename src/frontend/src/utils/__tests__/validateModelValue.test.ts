import type { APITemplateType } from "@/types/api";
import { findModelFieldKeys, validateModelValue } from "../model-node-helpers";

const openAiOption = { name: "gpt-6-luna", provider: "OpenAI", icon: "OpenAI" };

function templateWith(modelType: string, options: unknown[]): APITemplateType {
  return {
    decision_model: {
      type: "model",
      model_type: modelType,
      options,
      value: [{ name: "jev-latest", provider: "TypeSafe", icon: "Bot" }],
    },
  } as unknown as APITemplateType;
}

describe("validateModelValue", () => {
  it("keeps a saved decision model that another provider would replace", () => {
    const template = templateWith("decision", [openAiOption]);
    expect(validateModelValue(template, "decision_model")).toBe(template);
  });

  it("keeps a saved decision model when no decision provider is configured", () => {
    const template = templateWith("decision", []);
    expect(validateModelValue(template, "decision_model")).toBe(template);
  });

  it("leaves an empty decision field empty until the user picks a model", () => {
    const template = templateWith("decision", [openAiOption]);
    template.decision_model.value = [];
    expect(validateModelValue(template, "decision_model")).toBe(template);
    expect(template.decision_model.value).toEqual([]);
  });

  it("leaves a field of unknown kind for the picker to refuse", () => {
    const template = templateWith("rerank", [openAiOption]);
    expect(validateModelValue(template, "decision_model")).toBe(template);
  });

  it("still replaces an unavailable language model with the first option", () => {
    const result = validateModelValue(
      templateWith("language", [openAiOption]),
      "decision_model",
    );
    expect(result.decision_model.value[0].name).toBe("gpt-6-luna");
  });
});

describe("findModelFieldKeys", () => {
  it("returns every shown model field so each one is refreshed", () => {
    const template = {
      model: { type: "model", show: true },
      prompt: { type: "str", show: true },
      decision_model: { type: "model" },
    } as unknown as APITemplateType;
    expect(findModelFieldKeys(template)).toEqual(["model", "decision_model"]);
  });

  it("skips hidden model fields", () => {
    const template = {
      model: { type: "model", show: false },
      decision_model: { type: "model", show: true },
    } as unknown as APITemplateType;
    expect(findModelFieldKeys(template)).toEqual(["decision_model"]);
  });

  it("falls back to the first model field when every one is hidden", () => {
    const template = {
      model: { type: "model", show: false },
      decision_model: { type: "model", show: false },
    } as unknown as APITemplateType;
    expect(findModelFieldKeys(template)).toEqual(["model"]);
  });

  it("returns nothing for a node without model fields", () => {
    const template = {
      prompt: { type: "str" },
    } as unknown as APITemplateType;
    expect(findModelFieldKeys(template)).toEqual([]);
  });
});
