import type { APITemplateType } from "@/types/api";
import { validateModelValue } from "../model-node-helpers";

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

  it("still replaces an unavailable language model with the first option", () => {
    const result = validateModelValue(
      templateWith("language", [openAiOption]),
      "decision_model",
    );
    expect(result.decision_model.value[0].name).toBe("gpt-6-luna");
  });
});
