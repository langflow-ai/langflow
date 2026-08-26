import type { AllNodeType } from "@/types/flow";
import { getNodeAriaLabel, getNodeAriaLabels } from "../get-node-aria-label";

const t = (key: string, options?: Record<string, unknown>) => {
  const translations: Record<string, string> = {
    "noteNode.ariaLabel": "Note node",
    "flow.nodeAriaLabel": "{{name}} node",
    "flow.nodeAriaLabelOrdinal": "{{label}} {{ordinal}}",
  };
  const raw = translations[key] ?? key;
  if (!options) return raw;
  return raw.replace(/\{\{(\w+)\}\}/g, (_, k) => String(options[k] ?? ""));
};

const genericNode = (displayName: string, type = "ChatInput") =>
  ({
    type: "genericNode",
    data: { node: { display_name: displayName }, type },
  }) as unknown as AllNodeType;

const noteNode = () =>
  ({
    type: "noteNode",
    data: { node: { display_name: "" }, type: "" },
  }) as unknown as AllNodeType;

describe("getNodeAriaLabel", () => {
  it("returns a fixed, non-blank label for note nodes regardless of display_name", () => {
    expect(getNodeAriaLabel(noteNode(), t)).toBe("Note node");
  });

  it("uses the component display_name for regular nodes", () => {
    expect(getNodeAriaLabel(genericNode("Chat Input"), t)).toBe(
      "Chat Input node",
    );
  });

  it("falls back to the node type when display_name is an empty string", () => {
    expect(getNodeAriaLabel(genericNode("", "ChatInput"), t)).toBe(
      "ChatInput node",
    );
  });
});

describe("getNodeAriaLabels", () => {
  it("gives same-type nodes distinct accessible names", () => {
    const labels = getNodeAriaLabels(
      [genericNode("Chat Input"), genericNode("Chat Input")],
      t,
    );

    expect(labels).toEqual(["Chat Input node 1", "Chat Input node 2"]);
    expect(new Set(labels).size).toBe(labels.length);
  });

  it("leaves a node whose label is unique exactly as it is today", () => {
    const labels = getNodeAriaLabels(
      [genericNode("Chat Input"), genericNode("Chat Output", "ChatOutput")],
      t,
    );

    expect(labels).toEqual(["Chat Input node", "Chat Output node"]);
  });

  it("only numbers the colliding group, not the unique nodes around it", () => {
    const labels = getNodeAriaLabels(
      [
        genericNode("Chat Input"),
        genericNode("Agent", "Agent"),
        genericNode("Chat Input"),
        genericNode("Chat Output", "ChatOutput"),
      ],
      t,
    );

    expect(labels).toEqual([
      "Chat Input node 1",
      "Agent node",
      "Chat Input node 2",
      "Chat Output node",
    ]);
  });

  it("disambiguates duplicate note nodes too", () => {
    expect(getNodeAriaLabels([noteNode(), noteNode()], t)).toEqual([
      "Note node 1",
      "Note node 2",
    ]);
  });

  it("produces stable ordinals across recomputes of the same node list", () => {
    const nodes = [
      genericNode("Chat Input"),
      genericNode("Chat Input"),
      genericNode("Chat Input"),
    ];

    expect(getNodeAriaLabels(nodes, t)).toEqual(getNodeAriaLabels(nodes, t));
    expect(getNodeAriaLabels(nodes, t)).toEqual([
      "Chat Input node 1",
      "Chat Input node 2",
      "Chat Input node 3",
    ]);
  });
});
