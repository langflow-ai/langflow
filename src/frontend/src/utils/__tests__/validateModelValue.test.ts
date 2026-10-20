import type { APITemplateType } from "@/types/api";
import { findModelFieldKey, validateModelValue } from "../model-node-helpers";

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

  it("still replaces an unavailable language model with the first option", () => {
    const result = validateModelValue(
      templateWith("language", [openAiOption]),
      "decision_model",
    );
    expect(result.decision_model.value[0].name).toBe("gpt-6-luna");
  });
});

describe("findModelFieldKey", () => {
  it("refreshes the model field that is shown", () => {
    const template = {
      decision_model: { type: "model", show: false },
      model: { type: "model", show: true },
    } as unknown as APITemplateType;
    expect(findModelFieldKey(template)).toBe("model");
  });
});
