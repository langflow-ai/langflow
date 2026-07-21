/**
 * LE-1929: flows saved when the node card was `w-96` (384px) kept `width: 384`. React Flow then
 * uses that stale width to place the right-side output handle ~64px past the actual `w-80` (320px)
 * card, so edges render detached from the handle. Reconciling drops the persisted dimensions so
 * React Flow re-measures the real DOM size. noteNodes are user-resizable and must be preserved.
 */

import { reconcileStaleGenericNodeDimensions } from "../reactflowUtils";

describe("reconcileStaleGenericNodeDimensions", () => {
  it("drops stale width/height/measured from genericNodes so React Flow re-measures", () => {
    const nodes: any[] = [
      {
        id: "Memory-1",
        type: "genericNode",
        width: 384,
        height: 366,
        measured: { width: 384, height: 366 },
        position: { x: 0, y: 0 },
        data: {},
      },
    ];

    reconcileStaleGenericNodeDimensions(nodes as any);

    expect(nodes[0].width).toBeUndefined();
    expect(nodes[0].height).toBeUndefined();
    expect(nodes[0].measured).toBeUndefined();
  });

  it("preserves dimensions on noteNodes (they are user-resizable)", () => {
    const nodes: any[] = [
      {
        id: "note-1",
        type: "noteNode",
        width: 500,
        height: 300,
        measured: { width: 500, height: 300 },
        position: { x: 0, y: 0 },
        data: {},
      },
    ];

    reconcileStaleGenericNodeDimensions(nodes as any);

    expect(nodes[0].width).toBe(500);
    expect(nodes[0].height).toBe(300);
    expect(nodes[0].measured).toEqual({ width: 500, height: 300 });
  });
});
