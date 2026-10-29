import type { FlowModelPicker } from "@/controllers/API/queries/evals/types";
import { buildModelOverrides, pickerKey } from "../modelOverrideUtils";

const GPT = [{ name: "gpt-4o", provider: "OpenAI", metadata: {} }];
const MINI = [
  { name: "gpt-4o-mini", provider: "OpenAI", icon: "OpenAI", metadata: {} },
];

const picker = (node_id: string): FlowModelPicker => ({
  node_id,
  component: "Agent",
  field: "model",
  display_name: "Language Model",
  model_type: "language",
  value: GPT,
});

describe("buildModelOverrides", () => {
  it("should send only the pickers whose model changed", () => {
    const pickers = [picker("Agent-1"), picker("Agent-2")];
    const chosen = {
      [pickerKey(pickers[0])]: MINI,
      [pickerKey(pickers[1])]: GPT,
    };

    expect(buildModelOverrides(pickers, chosen)).toEqual([
      { node_id: "Agent-1", field: "model", value: MINI },
    ]);
  });

  it("should send nothing when no model was chosen", () => {
    expect(buildModelOverrides([picker("Agent-1")], {})).toEqual([]);
  });

  it("should ignore a choice for a picker the flow no longer has", () => {
    expect(
      buildModelOverrides([picker("Agent-1")], { "Gone-1::model": MINI }),
    ).toEqual([]);
  });
});
