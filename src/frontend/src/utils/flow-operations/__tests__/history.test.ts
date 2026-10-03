import type { RecordedOperation, RevisionEntry } from "@/types/flow/revision";
import type { FlowGraph } from "../apply";
import {
  buildHistoryTimeline,
  entryContaining,
  graphAt,
  lastRevision,
  operationAt,
} from "../history";

const node = (id: string, text = "hi") => ({
  id,
  data: { node: { template: { text: { value: text } } } },
});

function setText(revision: number, id: string, value: unknown) {
  return {
    revision,
    actor: { id: "u1", username: "alice" },
    request_id: `r${revision}`,
    labels: {},
    operation: {
      type: "update_nodes",
      updates: [
        {
          id,
          op: "set_field",
          path: ["data", "node", "template", "text", "value"],
          value,
        },
      ],
    },
  } satisfies RecordedOperation;
}

function entry(operations: RecordedOperation[]): RevisionEntry {
  return {
    id: `e${operations[0].revision}`,
    start_revision: operations[0].revision,
    end_revision: operations[operations.length - 1].revision,
    created_at: null,
    actors: [],
    request_ids: [],
    versions: [],
    operations,
  };
}

const base: FlowGraph = { nodes: [node("a")], edges: [] };

describe("buildHistoryTimeline", () => {
  it("keeps the graph at every revision, across entries", () => {
    const entries = [
      entry([setText(1, "a", "one"), setText(2, "a", "two")]),
      entry([setText(3, "a", "three")]),
    ];

    const timeline = buildHistoryTimeline({
      flowId: "f",
      baseRevision: 0,
      base,
      entries,
    });

    expect(lastRevision(timeline)).toBe(3);
    const textAt = (revision: number) =>
      (graphAt(timeline, revision)?.nodes[0] as ReturnType<typeof node>).data
        .node.template.text.value;
    expect([0, 1, 2, 3].map(textAt)).toEqual(["hi", "one", "two", "three"]);
    expect(operationAt(timeline, 0)).toBeNull();
    expect(operationAt(timeline, 2)?.request_id).toBe("r2");
    expect(graphAt(timeline, 4)).toBeNull();
    expect(base.nodes[0]).toEqual(node("a"));
  });

  it("replays redacted secrets that change a value's type", () => {
    // The history API returns a pasted key as null where the graph had "".
    const timeline = buildHistoryTimeline({
      flowId: "f",
      baseRevision: 0,
      base: { nodes: [node("a", "")], edges: [] },
      entries: [
        entry([setText(1, "a", null)]),
        entry([setText(2, "a", "OPENAI_API_KEY")]),
      ],
    });

    expect(lastRevision(timeline)).toBe(2);
  });

  it("stops at a missing revision instead of skipping it", () => {
    const timeline = buildHistoryTimeline({
      flowId: "f",
      baseRevision: 0,
      base,
      entries: [entry([setText(1, "a", "one")]), entry([setText(3, "a", "x")])],
    });

    expect(lastRevision(timeline)).toBe(1);
  });

  it("stops at an operation that does not apply", () => {
    const timeline = buildHistoryTimeline({
      flowId: "f",
      baseRevision: 0,
      base,
      entries: [entry([setText(1, "a", "one"), setText(2, "missing", "x")])],
    });

    expect(lastRevision(timeline)).toBe(1);
    expect(timeline.operations).toHaveLength(1);
  });
});

describe("entryContaining", () => {
  it("finds the entry a revision inside or at the end of belongs to", () => {
    const entries = [
      entry([setText(1, "a", "x"), setText(2, "a", "y")]),
      entry([setText(3, "a", "z")]),
    ];

    expect(entryContaining(entries, 1)?.id).toBe("e1");
    expect(entryContaining(entries, 2)?.id).toBe("e1");
    expect(entryContaining(entries, 3)?.id).toBe("e3");
    expect(entryContaining(entries, 0)).toBeUndefined();
  });
});
