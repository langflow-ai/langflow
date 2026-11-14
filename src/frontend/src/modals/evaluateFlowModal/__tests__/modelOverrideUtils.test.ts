import type { FlowModelPicker } from "@/controllers/API/queries/evals/types";
import {
  buildModelOverrides,
  effectiveModelNames,
  pickerKey,
  versionsMissModels,
} from "../modelOverrideUtils";

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

describe("versionsMissModels", () => {
  const unset = { ...picker("Agent-2"), value: [] };

  it("should flag a version that leaves a picker saved empty without a model", () => {
    const pickers = [picker("Agent-1"), unset];
    const filled = { key: 0, chosen: { [pickerKey(unset)]: MINI } };
    const empty = { key: 1, chosen: {} };

    expect(versionsMissModels(pickers, [filled])).toBe(false);
    expect(versionsMissModels(pickers, [filled, empty])).toBe(true);
    expect(versionsMissModels([picker("Agent-1")], [empty])).toBe(false);
  });
});

describe("effectiveModelNames", () => {
  it("should name the override where there is one and the flow's model elsewhere", () => {
    const pickers = [picker("Agent-1"), picker("Agent-2")];
    const overrides = buildModelOverrides(pickers, {
      [pickerKey(pickers[1])]: MINI,
    });

    expect(effectiveModelNames(pickers, [])).toEqual(["gpt-4o"]);
    expect(effectiveModelNames(pickers, overrides)).toEqual([
      "gpt-4o",
      "gpt-4o-mini",
    ]);
  });
});
