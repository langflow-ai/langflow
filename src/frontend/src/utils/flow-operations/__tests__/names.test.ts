import type { RecordedOperation } from "@/types/flow/revision";
import { collectHistoryNames, flowNames } from "../names";

const node = (id: string, name: string) => ({
  id,
  data: { node: { display_name: name, template: {} } },
});

function recorded(
  operation: RecordedOperation["operation"],
): RecordedOperation {
  return {
    revision: 1,
    actor: { id: "u1", username: "alice" },
    request_id: "r1",
    operation,
  };
}

const rename = (id: string, value: unknown) =>
  recorded({
    type: "update_nodes",
    updates: [
      { id, op: "set_field", path: ["data", "node", "display_name"], value },
    ],
  });

describe("collectHistoryNames", () => {
  it("keeps the latest name the history shows for each node", () => {
    const names = collectHistoryNames(
      { nodes: [node("a", "Prompt")], edges: [] },
      [
        recorded({ type: "add_nodes", nodes: [node("b", "Agent")] }),
        rename("a", "Summary prompt"),
        rename("b", ""),
        rename("b", 3),
        recorded({
          type: "update_nodes",
          updates: [
            {
              id: "b",
              op: "set_field",
              path: ["data", "node", "template", "display_name"],
              value: "not a node name",
            },
          ],
        }),
      ],
    );

    expect(Object.fromEntries(names.nodes)).toEqual({
      a: "Summary prompt",
      b: "Agent",
    });
  });

  it("keeps every edge's endpoints from the base graph and added edges", () => {
    const names = collectHistoryNames(
      {
        nodes: [],
        edges: [{ id: "e1", source: "a", target: "b" }],
      },
      [
        recorded({
          type: "add_edges",
          edges: [{ id: "e2", source: "b", target: "c" }],
        }),
      ],
    );

    expect(Object.fromEntries(names.edges)).toEqual({
      e1: { source: "a", target: "b" },
      e2: { source: "b", target: "c" },
    });
  });
});

describe("flowNames", () => {
  const history = collectHistoryNames(
    { nodes: [node("a", "Old name"), node("gone", "Deleted one")], edges: [] },
    [],
  );

  it("names a node from the flow as it is now, then from history, then by id", () => {
    const names = flowNames({ nodes: [node("a", "Current name")] }, history);

    expect(names.node("a")).toBe("Current name");
    expect(names.node("gone")).toBe("Deleted one");
    expect(names.node("never")).toBe("never");
  });

  it("works without a flow or a history", () => {
    expect(flowNames(null).node("x")).toBe("x");
    expect(flowNames(undefined, null).edge("e")).toBeUndefined();
  });
});
