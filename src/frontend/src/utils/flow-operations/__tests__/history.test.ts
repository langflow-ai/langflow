import { cloneDeep } from "lodash";
import type { RecordedOperation, RevisionEntry } from "@/types/flow/revision";
import golden from "../../../../../lfx/tests/unit/services/flow_operations/fixtures/apply_cases.json";
import propertyCases from "../../../../../lfx/tests/unit/services/flow_operations/fixtures/property_cases.json";
import {
  applyFlowOperations,
  type FlowGraph,
  type FlowOperation,
} from "../apply";
import { canonicalGraphJson } from "../canonical";
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

function recorded(
  revision: number,
  operation: RecordedOperation["operation"],
): RecordedOperation {
  return {
    revision,
    actor: { id: "u1", username: "alice" },
    request_id: `r${revision}`,
    labels: {},
    operation,
  };
}

function setText(revision: number, id: string, value: unknown) {
  return recorded(revision, {
    type: "update_nodes",
    updates: [
      {
        id,
        op: "set_field",
        path: ["data", "node", "template", "text", "value"],
        value,
      },
    ],
  });
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

function timelineOf(base: FlowGraph, operations: FlowOperation[]) {
  return buildHistoryTimeline({
    flowId: "f",
    baseRevision: 0,
    base,
    entries: [
      entry(operations.map((operation, i) => recorded(i + 1, operation))),
    ],
  });
}

const canonical = (graph: unknown) =>
  canonicalGraphJson(graph as Record<string, unknown>);

const base: FlowGraph = { nodes: [node("a")], edges: [] };

describe("buildHistoryTimeline", () => {
  it("reaches the graph at every revision, across entries", () => {
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
    expect([3, 1, 2, 0].map(textAt)).toEqual(["three", "one", "two", "hi"]);
    expect(operationAt(timeline, 0)).toBeNull();
    expect(operationAt(timeline, 2)?.request_id).toBe("r2");
    expect(graphAt(timeline, 4)).toBeNull();
    expect(graphAt(timeline, -1)).toBeNull();
    expect(base.nodes[0]).toEqual(node("a"));
  });

  it("holds one graph and an inverse per revision, not a graph per revision", () => {
    const timeline = timelineOf(
      base,
      ["one", "two"].map((value, i) => setText(i + 1, "a", value).operation),
    );

    expect(timeline.cursor.revision).toBe(2);
    expect(timeline.inverses).toEqual([
      [
        {
          type: "update_nodes",
          updates: [
            {
              id: "a",
              op: "set_field",
              path: ["data", "node", "template", "text", "value"],
              value: "hi",
            },
          ],
        },
      ],
      [
        {
          type: "update_nodes",
          updates: [
            {
              id: "a",
              op: "set_field",
              path: ["data", "node", "template", "text", "value"],
              value: "one",
            },
          ],
        },
      ],
    ]);
  });

  it("leaves a graph it returned unchanged when playback moves on", () => {
    const timeline = timelineOf(base, [setText(1, "a", "one").operation]);
    const atOne = graphAt(timeline, 1)!;
    const snapshot = cloneDeep(atOne);

    graphAt(timeline, 0);

    expect(atOne).toEqual(snapshot);
  });

  it("replays redacted secrets that change a value's type, both ways", () => {
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
    expect(graphAt(timeline, 0)).not.toBeNull();
    expect(graphAt(timeline, 2)).not.toBeNull();
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

  it("collects the names the history shows", () => {
    const timeline = buildHistoryTimeline({
      flowId: "f",
      baseRevision: 0,
      base: {
        nodes: [
          {
            id: "a",
            data: { node: { display_name: "Prompt", template: {} } },
          },
        ],
        edges: [],
      },
      entries: [
        entry([
          recorded(1, {
            type: "update_nodes",
            updates: [
              {
                id: "a",
                op: "set_field",
                path: ["data", "node", "display_name"],
                value: "Renamed",
              },
            ],
          }),
          recorded(2, {
            type: "add_nodes",
            nodes: [
              {
                id: "b",
                data: { node: { display_name: "Agent", template: {} } },
              },
            ],
          }),
          recorded(3, {
            type: "add_edges",
            edges: [{ id: "e", source: "a", target: "b" }],
          }),
        ]),
      ],
    });

    expect(Object.fromEntries(timeline.names.nodes)).toEqual({
      a: "Renamed",
      b: "Agent",
    });
    expect(timeline.names.edges.get("e")).toEqual({ source: "a", target: "b" });
  });
});

describe("playback steps back and forth", () => {
  const document = propertyCases as unknown as {
    base: FlowGraph;
    sequences: { name: string; transactions: FlowOperation[][] }[];
  };

  it.each(document.sequences.map((s) => [s.name, s]))(
    "%s: every revision, in any order, is the forward replay",
    (_name, sequence) => {
      const operations = sequence.transactions.flat();
      const expected = [canonical(document.base)];
      let graph = document.base;
      for (const operation of operations) {
        graph = applyFlowOperations(graph, [operation]).flowData;
        expected.push(canonical(graph));
      }
      const timeline = timelineOf(cloneDeep(document.base), operations);
      expect(lastRevision(timeline)).toBe(operations.length);

      const last = operations.length;
      const order = [
        ...Array.from({ length: last + 1 }, (_, i) => last - i),
        ...Array.from({ length: last + 1 }, (_, i) => i),
        last,
        0,
        Math.floor(last / 2),
        1,
        last - 1,
      ];
      for (const revision of order) {
        expect(canonical(graphAt(timeline, revision))).toBe(expected[revision]);
      }
    },
  );

  it("jumps across thousands of revisions", () => {
    const count = 2000;
    const timeline = timelineOf(
      base,
      Array.from(
        { length: count },
        (_, i) => setText(i + 1, "a", `v${i + 1}`).operation,
      ),
    );
    const text = (graph: FlowGraph | null) =>
      (graph?.nodes[0] as ReturnType<typeof node>).data.node.template.text
        .value;

    expect(text(graphAt(timeline, 0))).toBe("hi");
    expect(text(graphAt(timeline, count))).toBe(`v${count}`);
    expect(text(graphAt(timeline, 777))).toBe("v777");
    expect(text(graphAt(timeline, 0))).toBe("hi");
  });
});

describe("inverse operations", () => {
  type GoldenCase = {
    name: string;
    base: FlowGraph;
    operations: FlowOperation[];
    error?: string;
  };
  const successes = (golden as unknown as { cases: GoldenCase[] }).cases
    .filter((testCase) => !testCase.error)
    .map((testCase) => [testCase.name, testCase] as const);

  function undo(graph: FlowGraph, inverses: FlowOperation[][]): FlowGraph {
    let result = graph;
    for (const inverse of [...inverses].reverse()) {
      result = applyFlowOperations(result, inverse, {
        restoring: true,
      }).flowData;
    }
    return result;
  }

  it.each(successes)("undo %s", (_name, testCase) => {
    const { flowData, inverseOperations } = applyFlowOperations(
      cloneDeep(testCase.base),
      cloneDeep(testCase.operations),
      { inverse: true },
    );

    expect(canonical(undo(flowData, inverseOperations!))).toBe(
      canonical(testCase.base),
    );
  });

  it("undoes every transaction of the property fixture", () => {
    const document = propertyCases as unknown as {
      base: FlowGraph;
      sequences: { transactions: FlowOperation[][] }[];
    };
    for (const sequence of document.sequences) {
      let graph = document.base;
      for (const transaction of sequence.transactions) {
        const result = applyFlowOperations(graph, transaction, {
          inverse: true,
        });
        expect(
          canonical(undo(result.flowData, result.inverseOperations!)),
        ).toBe(canonical(graph));
        graph = result.flowData;
      }
    }
  });

  const keyed = (): FlowGraph => ({
    nodes: [
      {
        id: "k",
        data: {
          node: {
            outputs: [{ name: "a" }, { name: "b" }, { name: "c" }],
            template: {
              rows: {
                type: "table",
                // Not in (_pos, _id) order, as a stored table may be.
                value: [
                  { _id: "r2", _pos: "a1", v: "y" },
                  { _id: "r1", _pos: "a0", v: "x" },
                ],
              },
            },
          },
        },
      },
    ],
    edges: [],
  });
  const roundTrip = (updates: unknown[]) => {
    const before = keyed();
    const { flowData, inverseOperations } = applyFlowOperations(
      before,
      [{ type: "update_nodes", updates }],
      { inverse: true },
    );
    return {
      before,
      after: flowData,
      undone: undo(flowData, inverseOperations!),
    };
  };

  it("puts a removed output back where it was", () => {
    const { after, undone, before } = roundTrip([
      {
        id: "k",
        op: "delete_field",
        path: ["data", "node", "outputs", { key: "a" }],
      },
    ]);

    expect(canonical(after)).not.toBe(canonical(before));
    expect(undone.nodes[0]).toEqual(before.nodes[0]);
  });

  it("puts back the order of a table a write sorted", () => {
    const { after, undone, before } = roundTrip([
      {
        id: "k",
        op: "set_field",
        path: ["data", "node", "template", "rows", "value", { id: "r3" }],
        value: { _id: "r3", _pos: "a2", v: "z" },
      },
    ]);

    expect(
      (after.nodes[0] as ReturnType<typeof keyed>["nodes"][0]).data,
    ).toMatchObject({
      node: {
        template: {
          rows: { value: [{ _id: "r1" }, { _id: "r2" }, { _id: "r3" }] },
        },
      },
    });
    expect(undone.nodes[0]).toEqual(before.nodes[0]);
  });

  it("undoes writes to one path in the reverse order they were made", () => {
    const { undone, before } = roundTrip([
      {
        id: "k",
        op: "set_field",
        path: ["data", "node", "outputs", { key: "d" }],
        value: { name: "d" },
      },
      {
        id: "k",
        op: "set_field",
        path: ["data", "node", "outputs", { key: "d" }, "hidden"],
        value: true,
      },
      {
        id: "k",
        op: "delete_field",
        path: ["data", "node", "outputs", { key: "b" }],
      },
    ]);

    expect(undone.nodes[0]).toEqual(before.nodes[0]);
  });

  it("restores the edges a removed node took with it, even stale ones", () => {
    const graph: FlowGraph = {
      nodes: [
        { id: "s", data: { node: { template: {}, outputs: [{ name: "o" }] } } },
        { id: "d", data: { node: { template: { one: { type: "str" } } } } },
      ],
      edges: [
        {
          id: "stale",
          source: "s",
          target: "d",
          data: {
            sourceHandle: { name: "o" },
            targetHandle: { fieldName: "gone" },
          },
        },
      ],
    };
    const { flowData, inverseOperations } = applyFlowOperations(
      graph,
      [{ type: "delete_nodes", ids: ["d"] }],
      { inverse: true },
    );

    expect(flowData.edges).toEqual([]);
    expect(canonical(undo(flowData, inverseOperations!))).toBe(
      canonical(graph),
    );
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
