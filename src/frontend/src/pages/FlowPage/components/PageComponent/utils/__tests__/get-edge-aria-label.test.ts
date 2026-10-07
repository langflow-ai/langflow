import type { AllNodeType, EdgeType } from "@/types/flow";
import { getEdgeAriaLabel } from "../get-edge-aria-label";

const t = (key: string, options?: Record<string, unknown>) => {
  const translations: Record<string, string> = {
    "edge.ariaLabel": "Edge from {{source}} to {{target}}",
  };
  const raw = translations[key] ?? key;
  if (!options) return raw;
  return raw.replace(/\{\{(\w+)\}\}/g, (_, k) => String(options[k] ?? ""));
};

function makeNode(id: string, display_name?: string): AllNodeType {
  return {
    id,
    data: { node: { display_name } },
  } as unknown as AllNodeType;
}

const baseEdge = { source: "n1", target: "n2" } as EdgeType;

describe("getEdgeAriaLabel", () => {
  it("uses the source and target node display names", () => {
    const nodes: Record<string, AllNodeType> = {
      n1: makeNode("n1", "Chat Input"),
      n2: makeNode("n2", "Chat Output"),
    };
    const getNode = (id: string) => nodes[id];

    expect(getEdgeAriaLabel(baseEdge, getNode, t)).toBe(
      "Edge from Chat Input to Chat Output",
    );
  });

  it("falls back to the raw node id when a node cannot be found", () => {
    const getNode = () => undefined;

    expect(getEdgeAriaLabel(baseEdge, getNode, t)).toBe("Edge from n1 to n2");
  });

  it("falls back to the raw node id when display_name is missing", () => {
    const nodes: Record<string, AllNodeType> = {
      n1: makeNode("n1", undefined),
      n2: makeNode("n2", undefined),
    };
    const getNode = (id: string) => nodes[id];

    expect(getEdgeAriaLabel(baseEdge, getNode, t)).toBe("Edge from n1 to n2");
  });
});
