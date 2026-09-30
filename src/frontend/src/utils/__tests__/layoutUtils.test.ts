/**
 * Jest tests for the auto-layout fallback used by flows whose nodes carry no
 * `position` — e.g. payloads produced by `GET /api/v1/starter-projects/`, which
 * emits nodes without `position` and edges without `id`/`sourceHandle`/
 * `targetHandle`.
 *
 * Regression coverage for two defects:
 *  1. getLayoutedNodes passed `id: undefined` to ELK for edges and for ports
 *     derived from absent handles, so ELK threw
 *     `JsonImportException: Id must be a string or an integer: 'null'` for
 *     exactly the flows that needed the layout.
 *  2. processFlows never awaits processDataFromFlow, so the layout landed after
 *     the nodes had already been handed to React Flow, whose
 *     getNodePositionWithOrigin dereferences `node.position.x` unguarded.
 */

import type { AllNodeType, EdgeType } from "@/types/flow";
import { getFallbackGridPositions, getLayoutedNodes } from "../layoutUtils";
import { needsLayout, processFlows } from "../reactflowUtils";

const makeNode = (id: string): AllNodeType =>
  ({
    id,
    data: { id, type: id.split("-")[0], node: { template: {}, outputs: [] } },
  }) as unknown as AllNodeType;

// Shaped like a /starter-projects/ edge: no id, no sourceHandle, no targetHandle.
const makeHandlelessEdge = (source: string, target: string): EdgeType =>
  ({ source, target, data: {} }) as unknown as EdgeType;

const hasNumericPosition = (node: AllNodeType) =>
  !!node.position &&
  typeof node.position.x === "number" &&
  typeof node.position.y === "number" &&
  !Number.isNaN(node.position.x) &&
  !Number.isNaN(node.position.y);

describe("getFallbackGridPositions", () => {
  it("gives every node a numeric position", () => {
    const nodes = ["A", "B", "C", "D", "E"].map(makeNode);
    expect(getFallbackGridPositions(nodes).every(hasNumericPosition)).toBe(
      true,
    );
  });

  it("does not place two nodes at the same coordinates", () => {
    const positioned = getFallbackGridPositions(
      ["A", "B", "C", "D"].map(makeNode),
    );
    const coords = positioned.map((n) => `${n.position.x},${n.position.y}`);
    expect(new Set(coords).size).toBe(coords.length);
  });

  it("handles an empty node list", () => {
    expect(getFallbackGridPositions([])).toEqual([]);
  });
});

describe("needsLayout", () => {
  it("flags nodes with no position at all", () => {
    expect(needsLayout([makeNode("A")])).toBe(true);
  });

  it("flags nodes whose coordinates are not numbers", () => {
    const node = {
      ...makeNode("A"),
      position: { x: "12" as unknown as number, y: 0 },
    };
    expect(needsLayout([node])).toBe(true);
  });

  it("flags NaN coordinates", () => {
    const node = { ...makeNode("A"), position: { x: Number.NaN, y: 0 } };
    expect(needsLayout([node])).toBe(true);
  });

  it("flags non-finite coordinates", () => {
    const positive = {
      ...makeNode("A"),
      position: { x: Number.POSITIVE_INFINITY, y: 0 },
    };
    const negative = {
      ...makeNode("B"),
      position: { x: 0, y: Number.NEGATIVE_INFINITY },
    };
    expect(needsLayout([positive])).toBe(true);
    expect(needsLayout([negative])).toBe(true);
  });

  it("accepts well-formed positions", () => {
    const node = { ...makeNode("A"), position: { x: 0, y: 0 } };
    expect(needsLayout([node])).toBe(false);
  });
});

describe("getLayoutedNodes with handle-less edges", () => {
  it("lays out a graph whose edges have no id or handles", async () => {
    const nodes = ["ChatInput-a", "Prompt-b", "ChatOutput-c"].map(makeNode);
    const edges = [
      makeHandlelessEdge("ChatInput-a", "Prompt-b"),
      makeHandlelessEdge("Prompt-b", "ChatOutput-c"),
    ];

    const layouted = await getLayoutedNodes(nodes, edges);

    expect(layouted).toHaveLength(3);
    expect(layouted.every(hasNumericPosition)).toBe(true);
    // A real layered layout must separate the nodes, not stack them at 0,0.
    expect(new Set(layouted.map((n) => n.position.x)).size).toBeGreaterThan(1);
  });

  it("still positions every node when there are no edges", async () => {
    const nodes = ["A", "B"].map(makeNode);
    const layouted = await getLayoutedNodes(nodes, []);
    expect(layouted.every(hasNumericPosition)).toBe(true);
  });
});

describe("getLayoutedNodes when ELK rejects", () => {
  afterEach(() => {
    jest.dontMock("elkjs/lib/elk.bundled.js");
    jest.resetModules();
    jest.restoreAllMocks();
  });

  it("falls back to the deterministic grid instead of propagating", async () => {
    jest.resetModules();
    jest.doMock("elkjs/lib/elk.bundled.js", () => ({
      __esModule: true,
      default: class {
        layout = jest.fn().mockRejectedValue(new Error("ELK exploded"));
      },
    }));
    jest.spyOn(console, "error").mockImplementation(() => {});

    // Re-require so the module picks up the failing ELK singleton.
    const {
      getFallbackGridPositions: freshFallback,
      getLayoutedNodes: withFailingElk,
    } = require("../layoutUtils");

    const nodes = ["ChatInput-a", "Prompt-b", "ChatOutput-c"].map(makeNode);
    const edges = [makeHandlelessEdge("ChatInput-a", "Prompt-b")];

    const layouted = await withFailingElk(nodes, edges);

    // Resolves rather than rejecting, and every node is usable.
    expect(layouted).toHaveLength(3);
    expect(layouted.every(hasNumericPosition)).toBe(true);
    expect(layouted).toEqual(freshFallback(nodes));
  });
});

describe("processFlows on a flow with no positions", () => {
  const makeFlow = () =>
    ({
      id: "flow-1",
      name: "starter",
      description: "",
      is_component: false,
      data: {
        nodes: ["ChatInput-a", "ChatOutput-b"].map(makeNode),
        edges: [makeHandlelessEdge("ChatInput-a", "ChatOutput-b")],
      },
    }) as never;

  it("positions every node synchronously, before React Flow can adopt them", () => {
    const flow = makeFlow() as unknown as {
      data: { nodes: AllNodeType[] };
    };

    processFlows([flow as never]);

    // processFlows returns without awaiting the async layout, so the guarantee
    // has to hold at this point — this is the reference the store captures.
    expect(flow.data.nodes.every(hasNumericPosition)).toBe(true);
  });
});
