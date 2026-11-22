import {
  evaluatePlacement,
  filterPlaceableSelection,
  getPresentComponentTypes,
  placementKeysOf,
  TRIGGER_PLACEMENT_KEY,
} from "../componentConstraints";

function node(id: string, type?: string) {
  return { id, data: type === undefined ? {} : { type } };
}

function edge(id: string, source: string, target: string) {
  return { id, source, target };
}

describe("getPresentComponentTypes", () => {
  it("collects distinct component types and ignores nodes without a type", () => {
    const types = getPresentComponentTypes([
      node("a", "ChatInput"),
      node("b", "TextInput"),
      node("c", "ChatInput"),
      node("d"),
    ]);

    expect(types).toEqual(new Set(["ChatInput", "TextInput"]));
  });
});

describe("evaluatePlacement", () => {
  it("returns null for an unconstrained component", () => {
    expect(evaluatePlacement("TextInput", new Set(["Webhook"]))).toBeNull();
  });

  it("returns null when nothing conflicts", () => {
    expect(evaluatePlacement("ChatInput", new Set(["TextInput"]))).toBeNull();
  });

  it("flags a singleton violation when the same type is already present", () => {
    expect(evaluatePlacement("ChatInput", new Set(["ChatInput"]))).toEqual({
      type: "ChatInput",
      reason: "singleton",
    });
  });

  it("flags an exclusivity violation against a conflicting type", () => {
    expect(evaluatePlacement("ChatInput", new Set(["Webhook"]))).toEqual({
      type: "ChatInput",
      reason: "exclusivity",
      conflictingType: "Webhook",
    });
    expect(evaluatePlacement("Webhook", new Set(["ChatInput"]))).toEqual({
      type: "Webhook",
      reason: "exclusivity",
      conflictingType: "ChatInput",
    });
  });

  it("does not resolve prototype keys to inherited members", () => {
    expect(() =>
      evaluatePlacement("constructor", new Set(["Webhook"])),
    ).not.toThrow();
    expect(evaluatePlacement("constructor", new Set(["Webhook"]))).toBeNull();
  });
});

describe("filterPlaceableSelection", () => {
  it("keeps a non-conflicting selection untouched with no violations", () => {
    const selection = {
      nodes: [node("a", "TextInput"), node("b", "LLM")],
      edges: [edge("e", "a", "b")],
    };

    const result = filterPlaceableSelection(selection, [node("x", "Webhook")]);

    expect(result.nodes).toBe(selection.nodes);
    expect(result.edges).toBe(selection.edges);
    expect(result.violations).toEqual([]);
  });

  it("drops a pasted ChatInput when a Webhook is already in the flow", () => {
    const selection = {
      nodes: [node("a", "ChatInput"), node("b", "TextInput")],
      edges: [edge("e", "a", "b")],
    };

    const result = filterPlaceableSelection(selection, [node("x", "Webhook")]);

    expect(result.nodes.map((n) => n.id)).toEqual(["b"]);
    expect(result.edges).toEqual([]);
    expect(result.violations).toEqual([
      { type: "ChatInput", reason: "exclusivity", conflictingType: "Webhook" },
    ]);
  });

  it("drops a duplicate singleton already present in the flow", () => {
    const selection = { nodes: [node("a", "ChatInput")], edges: [] };

    const result = filterPlaceableSelection(selection, [
      node("x", "ChatInput"),
    ]);

    expect(result.nodes).toEqual([]);
    expect(result.violations).toEqual([
      { type: "ChatInput", reason: "singleton" },
    ]);
  });

  it("resolves a conflict introduced within the same selection (first wins)", () => {
    const selection = {
      nodes: [node("a", "ChatInput"), node("b", "Webhook")],
      edges: [edge("e", "a", "b")],
    };

    const result = filterPlaceableSelection(selection, []);

    expect(result.nodes.map((n) => n.id)).toEqual(["a"]);
    expect(result.edges).toEqual([]);
    expect(result.violations).toEqual([
      { type: "Webhook", reason: "exclusivity", conflictingType: "ChatInput" },
    ]);
  });

  it("keeps edges between surviving nodes", () => {
    const selection = {
      nodes: [node("a", "ChatInput"), node("b", "TextInput"), node("c", "LLM")],
      edges: [edge("e1", "a", "b"), edge("e2", "b", "c")],
    };

    const result = filterPlaceableSelection(selection, [node("x", "Webhook")]);

    expect(result.nodes.map((n) => n.id)).toEqual(["b", "c"]);
    expect(result.edges.map((e) => e.id)).toEqual(["e2"]);
  });

  it("handles an empty selection", () => {
    const result = filterPlaceableSelection({ nodes: [], edges: [] }, [
      node("x", "Webhook"),
    ]);

    expect(result.nodes).toEqual([]);
    expect(result.edges).toEqual([]);
    expect(result.violations).toEqual([]);
  });
});

describe("one trigger per flow", () => {
  const trigger = (id: string, type: string) => ({
    id,
    data: { type, node: { metadata: { trigger_kind: "x" } } },
  });

  it("gives a trigger node the trigger key besides its type", () => {
    expect(
      placementKeysOf("ScheduleTrigger", {
        metadata: { trigger_kind: "schedule" },
      }),
    ).toEqual(["ScheduleTrigger", TRIGGER_PLACEMENT_KEY]);
    expect(placementKeysOf("TextInput", { metadata: {} })).toEqual([
      "TextInput",
    ]);
  });

  it("ignores a trigger_kind that is not a string", () => {
    expect(placementKeysOf("X", { metadata: { trigger_kind: 1 } })).toEqual([
      "X",
    ]);
  });

  it("blocks a second trigger of a different kind", () => {
    const present = getPresentComponentTypes([trigger("a", "ScheduleTrigger")]);

    expect(
      evaluatePlacement(["SlackOnMessage", TRIGGER_PLACEMENT_KEY], present),
    ).toEqual({ type: TRIGGER_PLACEMENT_KEY, reason: "singleton" });
  });

  it("allows the first trigger", () => {
    expect(
      evaluatePlacement(["SlackOnMessage", TRIGGER_PLACEMENT_KEY], new Set()),
    ).toBeNull();
  });

  it("drops a pasted trigger when the flow already has one", () => {
    const result = filterPlaceableSelection(
      { nodes: [trigger("b", "SlackOnMessage"), node("c", "LLM")], edges: [] },
      [trigger("a", "ScheduleTrigger")],
    );

    expect(result.nodes.map((n) => n.id)).toEqual(["c"]);
    expect(result.violations).toEqual([
      { type: TRIGGER_PLACEMENT_KEY, reason: "singleton" },
    ]);
  });

  it("keeps only the first of two triggers pasted together", () => {
    const result = filterPlaceableSelection(
      {
        nodes: [
          trigger("a", "ScheduleTrigger"),
          trigger("b", "SlackOnMessage"),
        ],
        edges: [],
      },
      [],
    );

    expect(result.nodes.map((n) => n.id)).toEqual(["a"]);
  });
});
