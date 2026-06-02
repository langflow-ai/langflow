import type { CollaborationSelectionMarker } from "../collaboration-selection-markers";
import { resolveCollaborationEdgeSelectionTransforms } from "../use-collaboration-edge-selection-transforms";

const marker: CollaborationSelectionMarker = {
  targetId: "edge-1",
  kind: "edge",
  participants: [
    {
      user_id: "user-1",
      username: "ana",
      isCurrentUser: false,
      color: "#3b82f6",
    },
  ],
};

const edge = {
  id: "edge-1",
  source: "source",
  target: "target",
} as never;

function node(id: string, x: number, y: number) {
  return {
    id,
    type: "genericNode",
    position: { x, y },
    data: {},
  } as never;
}

describe("resolveCollaborationEdgeSelectionTransforms", () => {
  it("keeps resolving an edge marker after a connected node moves", () => {
    const nodeLookup = new Map();
    const initial = resolveCollaborationEdgeSelectionTransforms({
      edgeMarkers: [marker],
      edges: [edge],
      flowNodes: [node("source", 0, 0), node("target", 500, 0)],
      nodeLookup,
    });
    const moved = resolveCollaborationEdgeSelectionTransforms({
      edgeMarkers: [marker],
      edges: [edge],
      flowNodes: [node("source", 0, 0), node("target", 700, 120)],
      nodeLookup,
    });

    expect(initial.get("edge-1")).toEqual(expect.any(String));
    expect(moved.get("edge-1")).toEqual(expect.any(String));
    expect(moved.get("edge-1")).not.toBe(initial.get("edge-1"));
  });
});
