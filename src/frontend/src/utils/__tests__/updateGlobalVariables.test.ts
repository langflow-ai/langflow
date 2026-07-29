import type { APIClassType, InputFieldType } from "@/types/api";
import { updateGlobalVariables } from "../reactflowUtils";

type ModelMarker = "input_type" | "type" | "ordinary";

const makeField = (
  overrides: Partial<InputFieldType> = {},
): InputFieldType => ({
  type: "str",
  required: false,
  list: false,
  show: true,
  readonly: false,
  ...overrides,
});

const makeNode = (modelMarker: ModelMarker): APIClassType =>
  ({
    description: "",
    display_name:
      modelMarker === "ordinary" ? "Ordinary Component" : "Embedding Model",
    documentation: "",
    template: {
      api_key: makeField({
        display_name: "API Key",
        load_from_db: false,
        value: "",
      }),
      model: makeField(
        modelMarker === "input_type"
          ? { _input_type: "ModelInput" }
          : modelMarker === "type"
            ? { type: "model" }
            : { display_name: "Model" },
      ),
    },
  }) satisfies APIClassType;

describe("updateGlobalVariables", () => {
  const unavailableFields = { "API Key": "WATSONX_APIKEY" };
  const globalVariablesEntries = ["WATSONX_APIKEY", "OPENAI_API_KEY"];

  it.each<ModelMarker>(["input_type", "type"])(
    "does not apply generic API key defaults to unified model fields detected by %s",
    (modelMarker) => {
      const node = makeNode(modelMarker);

      updateGlobalVariables(node, unavailableFields, globalVariablesEntries);

      expect(node.template.api_key.value).toBe("");
      expect(node.template.api_key.load_from_db).toBe(false);
    },
  );

  it("continues to apply defaults when model is an ordinary string field", () => {
    const node = makeNode("ordinary");

    updateGlobalVariables(node, unavailableFields, globalVariablesEntries);

    expect(node.template.api_key.value).toBe("WATSONX_APIKEY");
    expect(node.template.api_key.load_from_db).toBe(true);
  });

  it("preserves an explicitly selected unified model global variable", () => {
    const node = makeNode("input_type");
    node.template.api_key.value = "OPENAI_API_KEY";
    node.template.api_key.load_from_db = true;

    updateGlobalVariables(node, unavailableFields, globalVariablesEntries);

    expect(node.template.api_key.value).toBe("OPENAI_API_KEY");
    expect(node.template.api_key.load_from_db).toBe(true);
  });

  it("clears a persisted unified model key that matches the legacy generic default", () => {
    const node = makeNode("input_type");
    node.template.api_key.value = "WATSONX_APIKEY";
    node.template.api_key.load_from_db = true;

    updateGlobalVariables(node, unavailableFields, globalVariablesEntries);

    expect(node.template.api_key.value).toBe("");
    expect(node.template.api_key.load_from_db).toBe(false);
  });
});
