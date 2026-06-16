import type {
  Diagram,
  DiagramEdge,
  DiagramNode,
} from "@/controllers/API/queries/lothal";
import {
  defaultNodeKind,
  edgeStyle,
  isEmptyDiagram,
  resolveEdgeKind,
  toFlowEdges,
  toFlowNodes,
} from "../canvasGraph";

const node = (over: Partial<DiagramNode>): DiagramNode => ({
  id: "n",
  type: "systemNode",
  position: { x: 0, y: 0 },
  data: { label: "Node" },
  ...over,
});

const edge = (over: Partial<DiagramEdge>): DiagramEdge => ({
  id: "e",
  source: "a",
  target: "b",
  data: { order: 1, label: "msg" },
  ...over,
});

describe("defaultNodeKind", () => {
  it("defaults actor→person and system→service", () => {
    expect(defaultNodeKind("actorNode")).toBe("person");
    expect(defaultNodeKind("systemNode")).toBe("service");
  });
});

describe("resolveEdgeKind", () => {
  it("defaults to sync when no render hint is present", () => {
    expect(resolveEdgeKind(edge({ data: { order: 1 } }))).toBe("sync");
  });
  it("uses the supplied kind", () => {
    expect(resolveEdgeKind(edge({ data: { order: 1, kind: "async" } }))).toBe(
      "async",
    );
  });
  it("falls back to the animated flag when kind is absent", () => {
    expect(resolveEdgeKind(edge({ animated: true, data: { order: 1 } }))).toBe(
      "async",
    );
  });
  it("prefers an explicit kind over the animated flag", () => {
    expect(
      resolveEdgeKind(
        edge({ animated: true, data: { order: 1, kind: "return" } }),
      ),
    ).toBe("return");
  });
});

describe("edgeStyle", () => {
  it("draws sync solid in the accent (no dash, not animated)", () => {
    const s = edgeStyle("sync");
    expect(s.animated).toBe(false);
    expect(s.strokeDasharray).toBeUndefined();
    expect(s.stroke).toBe("var(--accent)");
  });
  it("draws async dashed and animated", () => {
    const s = edgeStyle("async");
    expect(s.animated).toBe(true);
    expect(s.strokeDasharray).toBeTruthy();
  });
  it("draws return dashed and muted, not animated", () => {
    const s = edgeStyle("return");
    expect(s.animated).toBe(false);
    expect(s.strokeDasharray).toBeTruthy();
    expect(s.stroke).toBe("var(--ink-soft)");
  });
});

describe("toFlowNodes", () => {
  it("preserves id/type/position and fills the default kind", () => {
    const out = toFlowNodes([
      node({ id: "u", type: "actorNode", data: { label: "User" } }),
      node({ id: "s", type: "systemNode", data: { label: "API" } }),
    ]);
    expect(out).toHaveLength(2);
    expect(out[0].id).toBe("u");
    expect(out[0].type).toBe("actorNode");
    expect((out[0].data as { kind: string }).kind).toBe("person");
    expect((out[1].data as { kind: string }).kind).toBe("service");
  });

  it("keeps an explicit node kind", () => {
    const out = toFlowNodes([node({ data: { label: "DB", kind: "data" } })]);
    expect((out[0].data as { kind: string }).kind).toBe("data");
  });
});

describe("toFlowEdges", () => {
  it("maps every edge and sorts by data.order", () => {
    const out = toFlowEdges([
      edge({ id: "e2", data: { order: 2 } }),
      edge({ id: "e1", data: { order: 1 } }),
      edge({ id: "e3", data: { order: 3 } }),
    ]);
    expect(out.map((e) => e.id)).toEqual(["e1", "e2", "e3"]);
  });

  it("reads the rendered label from data.label", () => {
    const [e] = toFlowEdges([
      edge({ data: { order: 1, label: "create order" } }),
    ]);
    expect(e.label).toBe("create order");
  });

  it("applies the kind's visual treatment to each edge", () => {
    const [e] = toFlowEdges([edge({ data: { order: 1, kind: "async" } })]);
    expect(e.animated).toBe(true);
    expect(
      (e.style as { strokeDasharray?: string }).strokeDasharray,
    ).toBeTruthy();
    expect((e.data as { kind: string }).kind).toBe("async");
  });

  it("does not mutate the input array order", () => {
    const input = [
      edge({ id: "e2", data: { order: 2 } }),
      edge({ id: "e1", data: { order: 1 } }),
    ];
    toFlowEdges(input);
    expect(input.map((e) => e.id)).toEqual(["e2", "e1"]);
  });
});

describe("isEmptyDiagram", () => {
  const diagram = (nodes: DiagramNode[]): Diagram => ({
    nodes,
    edges: [],
  });
  it("is empty for undefined or zero nodes", () => {
    expect(isEmptyDiagram(undefined)).toBe(true);
    expect(isEmptyDiagram(diagram([]))).toBe(true);
  });
  it("is not empty when nodes are present", () => {
    expect(isEmptyDiagram(diagram([node({})]))).toBe(false);
  });
});
