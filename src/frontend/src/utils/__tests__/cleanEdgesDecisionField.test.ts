import { cleanEdges, scapedJSONStringfy } from "@/utils/reactflowUtils";

// A decision field takes no connection; an edge into one from an imported or
// API-created flow must be dropped on load, not kept and hidden.
it.each([
  { inputTypes: ["LanguageModel"], fieldInputTypes: [] },
  { inputTypes: [], fieldInputTypes: [] },
  { inputTypes: ["LanguageModel"], fieldInputTypes: ["LanguageModel"] },
])(
  "drops a decision-field edge with $inputTypes / $fieldInputTypes",
  ({ inputTypes, fieldInputTypes }) => {
    const llm = {
      id: "llm",
      type: "genericNode",
      position: { x: 0, y: 0 },
      data: {
        id: "llm",
        type: "LanguageModelComponent",
        node: {
          display_name: "LM",
          template: {},
          outputs: [
            {
              name: "model_output",
              types: ["LanguageModel"],
              selected: "LanguageModel",
            },
          ],
        },
      },
    };
    const router = {
      id: "router",
      type: "genericNode",
      position: { x: 0, y: 0 },
      data: {
        id: "router",
        type: "SmartRouter",
        node: {
          display_name: "Smart Router",
          outputs: [],
          template: {
            decision_model: {
              type: "model",
              model_type: "decision",
              input_types: fieldInputTypes,
              show: true,
              value: [],
            },
          },
        },
      },
    };
    const sourceHandle = scapedJSONStringfy({
      dataType: "LanguageModelComponent",
      id: "llm",
      name: "model_output",
      output_types: ["LanguageModel"],
    } as never);
    const targetHandle = scapedJSONStringfy({
      type: "model",
      fieldName: "decision_model",
      id: "router",
      inputTypes,
    } as never);
    const edges = [
      { id: "e1", source: "llm", target: "router", sourceHandle, targetHandle },
    ];

    const result = cleanEdges(
      [llm, router] as never,
      edges as never,
    ) as unknown;
    const kept = Array.isArray(result)
      ? result
      : (result as { edges: unknown[] }).edges;
    expect(kept).toHaveLength(0);
  },
);
