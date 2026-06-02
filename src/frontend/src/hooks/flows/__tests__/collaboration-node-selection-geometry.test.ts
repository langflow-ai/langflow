import { NODE_WIDTH } from "@/constants/constants";
import { resolveCollaborationNodeSelectionRect } from "../collaboration-node-selection-geometry";

describe("resolveCollaborationNodeSelectionRect", () => {
  it("uses flow-store position when React Flow has not measured yet", () => {
    const rect = resolveCollaborationNodeSelectionRect(
      {
        id: "node-1",
        position: { x: 120, y: 240 },
        data: {},
        type: "genericNode",
      } as never,
      undefined,
    );

    expect(rect).toEqual({
      x: 120,
      y: 240,
      width: NODE_WIDTH,
      height: 96,
    });
  });

  it("prefers React Flow absolute position and measured size when available", () => {
    const rect = resolveCollaborationNodeSelectionRect(
      {
        id: "node-1",
        position: { x: 10, y: 20 },
        data: {},
        type: "genericNode",
      } as never,
      {
        internals: { positionAbsolute: { x: 100, y: 200 } },
        measured: { width: 320, height: 180 },
      },
    );

    expect(rect).toEqual({
      x: 100,
      y: 200,
      width: 320,
      height: 180,
    });
  });
});
