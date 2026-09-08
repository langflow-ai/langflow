import { applySelectedChanges, diffGraphs } from "../flow-diff";

/** Mirrors the dialog: diff, then apply exactly what the person ticked. */
const node = (id: string) =>
  ({
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: { id, type: "Prompt", node: { display_name: id, template: {} } },
  }) as any;

const edge = (id: string, source: string, target: string) =>
  ({ id, source, target, data: {} }) as any;

describe("every selection the dialog counts is a selection it applies", () => {
  it("applies their new edge by bringing the new node it needs", () => {
    const base = { nodes: [node("a")], edges: [] };
    const mine = { nodes: [node("a")], edges: [] };
    // They added a node and wired it up.
    const theirs = {
      nodes: [node("a"), node("b")],
      edges: [edge("e1", "a", "b")],
    };

    const theirChanges = diffGraphs(base, theirs);
    const edgeChange = theirChanges.find((c) => c.targetKind === "edge")!;
    const nodeChange = theirChanges.find((c) => c.targetKind === "node")!;
    expect(edgeChange.targetKey).not.toBe(nodeChange.targetKey);

    // The person ticks the edge only. The dialog's footer counts selected.size.
    const selected = new Set([edgeChange.id]);
    const footerSaysTheirs = selected.size;
    const merged = applySelectedChanges(mine, theirs, theirChanges, selected);

    console.log(
      "footer promised:",
      footerSaysTheirs,
      "edges applied:",
      merged.edges.length,
    );
    expect(footerSaysTheirs).toBe(1);
    expect(merged.edges).toHaveLength(1);
  });
});
