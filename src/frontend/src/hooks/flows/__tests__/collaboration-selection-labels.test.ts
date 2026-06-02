import type { AllNodeType, EdgeType } from "@/types/flow";

import {
  formatEdgeSelectionLabel,
  getNodeDisplayLabel,
  resolveCollaborationSelectionLabel,
} from "../collaboration-selection-labels";

const parserNode = {
  id: "node-1",
  type: "genericNode",
  position: { x: 0, y: 0 },
  data: {
    id: "node-1",
    type: "Parser",
    node: {
      display_name: "Parser",
      template: {},
    },
  },
} as AllNodeType;

const outputNode = {
  id: "node-2",
  type: "genericNode",
  position: { x: 0, y: 0 },
  data: {
    id: "node-2",
    type: "Output",
    node: {
      display_name: "Output",
      template: {},
    },
  },
} as AllNodeType;

const edge = {
  id: "edge-1",
  source: "node-1",
  target: "node-2",
} as EdgeType;

describe("collaboration selection labels", () => {
  it("resolves node display labels", () => {
    expect(getNodeDisplayLabel(parserNode)).toBe("Parser");
    expect(
      resolveCollaborationSelectionLabel(
        { kind: "node", id: "node-1" },
        [parserNode],
        [],
      ),
    ).toBe("Parser");
  });

  it("resolves edge endpoint labels", () => {
    expect(formatEdgeSelectionLabel(edge, [parserNode, outputNode])).toBe(
      "Parser → Output",
    );
    expect(
      resolveCollaborationSelectionLabel(
        { kind: "edge", id: "edge-1" },
        [parserNode, outputNode],
        [edge],
      ),
    ).toBe("Parser → Output");
  });

  it("returns a stale label when the target no longer exists", () => {
    expect(
      resolveCollaborationSelectionLabel(
        { kind: "node", id: "missing-node" },
        [parserNode],
        [],
        { staleSelectionLabel: "Unavailable selection" },
      ),
    ).toBe("Unavailable selection");
  });
});
