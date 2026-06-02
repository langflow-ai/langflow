import type { OnSelectionChangeParams } from "@xyflow/react";

import {
  selectionTargetFromFlowSelection,
  serializeCollaborationSelectionTarget,
} from "../collaboration-selection-target";

describe("selectionTargetFromFlowSelection", () => {
  it("maps a single selected node", () => {
    const selection = {
      nodes: [{ id: "node-1" }],
      edges: [],
    } as OnSelectionChangeParams;

    expect(selectionTargetFromFlowSelection(selection)).toEqual({
      kind: "node",
      id: "node-1",
    });
  });

  it("maps a single selected edge", () => {
    const selection = {
      nodes: [],
      edges: [{ id: "edge-1" }],
    } as OnSelectionChangeParams;

    expect(selectionTargetFromFlowSelection(selection)).toEqual({
      kind: "edge",
      id: "edge-1",
    });
  });

  it("returns null for multi-selection and empty selection", () => {
    expect(
      selectionTargetFromFlowSelection({
        nodes: [{ id: "node-1" }, { id: "node-2" }],
        edges: [],
      } as OnSelectionChangeParams),
    ).toBeNull();
    expect(
      selectionTargetFromFlowSelection({
        nodes: [],
        edges: [],
      } as OnSelectionChangeParams),
    ).toBeNull();
    expect(selectionTargetFromFlowSelection(null)).toBeNull();
  });
});

describe("serializeCollaborationSelectionTarget", () => {
  it("serializes targets for deduplication", () => {
    expect(serializeCollaborationSelectionTarget(null)).toBe("");
    expect(
      serializeCollaborationSelectionTarget({ kind: "node", id: "node-1" }),
    ).toBe("node:node-1");
  });
});
