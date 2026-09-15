import type { APITemplateType } from "@/types/api";
import type { AllNodeType } from "@/types/flow";
import { diffGraphs } from "../flow-diff";
import {
  clearLoadRefreshes,
  recordLoadRefresh,
  withoutLoadRefreshes,
} from "../load-refreshes";

const template = (fields: Record<string, unknown>): APITemplateType =>
  Object.fromEntries(
    Object.entries(fields).map(([name, value]) => [
      name,
      { type: "str", show: true, value },
    ]),
  ) as unknown as APITemplateType;

const graph = (fields: Record<string, unknown>) => ({
  nodes: [
    {
      id: "model-1",
      type: "genericNode",
      position: { x: 0, y: 0 },
      data: {
        id: "model-1",
        type: "LanguageModelComponent",
        node: { display_name: "Language Model", template: template(fields) },
      },
    } as unknown as AllNodeType,
  ],
  edges: [],
});

describe("changes a flow's own opening made", () => {
  beforeEach(() => {
    clearLoadRefreshes();
    recordLoadRefresh(
      "flow-1",
      "model-1",
      template({ model: "", temperature: "0.1" }),
      template({ model: "gpt-6-astra", temperature: "0.1" }),
    );
  });

  it("should not credit the load-time refresh to the person", () => {
    const base = graph({ model: "", temperature: "0.1" });
    const mine = graph({ model: "gpt-6-astra", temperature: "0.1" });

    expect(withoutLoadRefreshes("flow-1", diffGraphs(base, mine))).toEqual([]);
  });

  it("should keep an edit the person made on top of the refresh", () => {
    const base = graph({ model: "", temperature: "0.1" });
    const mine = graph({ model: "claude", temperature: "0.1" });

    const kept = withoutLoadRefreshes("flow-1", diffGraphs(base, mine));

    expect(kept).toHaveLength(1);
    expect(kept[0].detail?.after).toBe("claude");
  });

  it("should keep other fields of the refreshed component", () => {
    const base = graph({ model: "", temperature: "0.1" });
    const mine = graph({ model: "gpt-6-astra", temperature: "0.9" });

    const kept = withoutLoadRefreshes("flow-1", diffGraphs(base, mine));

    expect(kept.map((change) => change.label)).toEqual(["temperature"]);
  });

  it("should keep the change when the baseline no longer holds what was refreshed", () => {
    const base = graph({ model: "claude", temperature: "0.1" });
    const mine = graph({ model: "gpt-6-astra", temperature: "0.1" });

    expect(withoutLoadRefreshes("flow-1", diffGraphs(base, mine))).toHaveLength(
      1,
    );
  });

  it("should not apply one flow's refresh to another flow", () => {
    const base = graph({ model: "", temperature: "0.1" });
    const mine = graph({ model: "gpt-6-astra", temperature: "0.1" });

    expect(withoutLoadRefreshes("flow-2", diffGraphs(base, mine))).toHaveLength(
      1,
    );
  });

  it("should forget the refresh once the flow is loaded again", () => {
    const base = graph({ model: "", temperature: "0.1" });
    const mine = graph({ model: "gpt-6-astra", temperature: "0.1" });

    clearLoadRefreshes("flow-1");

    expect(withoutLoadRefreshes("flow-1", diffGraphs(base, mine))).toHaveLength(
      1,
    );
  });
});
