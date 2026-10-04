import type {
  RecordedOperation,
  RevisionActor,
  RevisionEntry,
} from "@/types/flow/revision";
import type { FlowGraph } from "../apply";
import { changesAt, changesFrom, groupByActor, operationsAt } from "../changes";
import { buildHistoryTimeline } from "../history";

const alice: RevisionActor = { id: "u-alice", username: "alice" };
const bob: RevisionActor = { id: "u-bob", username: "bob" };

let nextRevision = 1;
function recorded(
  actor: RevisionActor,
  operation: RecordedOperation["operation"],
): RecordedOperation {
  const revision = nextRevision++;
  return { revision, actor, request_id: `r${revision}`, operation };
}

const setField = (id: string, field: string, value: unknown = "x") => ({
  id,
  op: "set_field",
  path: ["data", "node", "template", field, "value"],
  value,
});
const move = (id: string) => ({
  id,
  op: "set_field",
  path: ["position", "x"],
  value: 10,
});

beforeEach(() => {
  nextRevision = 1;
});

describe("changesFrom", () => {
  it("returns the nodes added and edited, their fields, and who did it", () => {
    const changes = changesFrom([
      recorded(alice, { type: "add_nodes", nodes: [{ id: "a" }] }),
      recorded(bob, {
        type: "update_nodes",
        updates: [setField("b", "temperature"), setField("b", "model")],
      }),
    ]);

    expect([...changes.nodes.keys()]).toEqual(["a", "b"]);
    expect(changes.nodes.get("a")).toMatchObject({
      actor: alice,
      added: true,
    });
    expect(changes.nodes.get("a")?.fields.size).toBe(0);
    expect(changes.nodes.get("b")).toMatchObject({ actor: bob, added: false });
    expect(Object.fromEntries(changes.nodes.get("b")!.fields)).toEqual({
      temperature: bob,
      model: bob,
    });
  });

  it("credits the last writer of a node and of each field", () => {
    const changes = changesFrom([
      recorded(alice, {
        type: "update_nodes",
        updates: [setField("a", "prompt"), setField("a", "model")],
      }),
      recorded(bob, {
        type: "update_nodes",
        updates: [setField("a", "model")],
      }),
    ]);

    const change = changes.nodes.get("a")!;
    expect(change.actor).toEqual(bob);
    expect(change.fields.get("prompt")).toEqual(alice);
    expect(change.fields.get("model")).toEqual(bob);
  });

  it("counts a moved or otherwise edited node, without fields", () => {
    const changes = changesFrom([
      recorded(alice, { type: "update_nodes", updates: [move("a")] }),
      recorded(alice, {
        type: "update_nodes",
        updates: [{ id: "b", op: "set_field", path: ["data", "showNode"] }],
      }),
    ]);

    expect(changes.nodes.get("a")?.fields.size).toBe(0);
    expect(changes.nodes.get("b")?.fields.size).toBe(0);
    expect([...changes.nodes.keys()]).toEqual(["a", "b"]);
  });

  it("keeps an added node marked as added after later edits", () => {
    const changes = changesFrom([
      recorded(alice, { type: "add_nodes", nodes: [{ id: "a" }] }),
      recorded(bob, { type: "update_nodes", updates: [setField("a", "text")] }),
    ]);

    expect(changes.nodes.get("a")).toMatchObject({ actor: bob, added: true });
    expect(changes.nodes.get("a")?.fields.get("text")).toEqual(bob);
  });

  it("narrows each node's operations to that node, oldest first", () => {
    const changes = changesFrom([
      recorded(alice, {
        type: "add_nodes",
        nodes: [{ id: "a" }, { id: "b" }],
      }),
      recorded(bob, {
        type: "update_nodes",
        updates: [setField("a", "text"), move("b")],
      }),
    ]);

    const ops = changes.nodes.get("b")!.operations;
    expect(ops.map((op) => op.revision)).toEqual([1, 2]);
    expect(ops[0].operation.nodes).toEqual([{ id: "b" }]);
    expect(ops[1].operation.updates).toEqual([move("b")]);
    expect(ops[1].actor).toEqual(bob);
  });

  it("returns added edges with who added them", () => {
    const changes = changesFrom([
      recorded(alice, {
        type: "add_edges",
        edges: [{ id: "e1", source: "a", target: "b" }],
      }),
      recorded(bob, {
        type: "add_edges",
        edges: [{ id: "e2", source: "b", target: "c" }],
      }),
    ]);

    expect(Object.fromEntries(changes.edges)).toEqual({ e1: alice, e2: bob });
  });

  it("lists deleted nodes and connections instead of highlighting them", () => {
    const ends = { e1: { source: "a", target: "b" } };
    const changes = changesFrom(
      [
        recorded(alice, {
          type: "update_nodes",
          updates: [setField("p", "template")],
        }),
        recorded(bob, { type: "delete_nodes", ids: ["p"] }),
        recorded(bob, { type: "delete_edges", ids: ["e1"] }),
        recorded(alice, { type: "delete_edges", ids: ["e2"] }),
      ],
      (id) => ends[id as keyof typeof ends],
    );

    expect(changes.nodes.has("p")).toBe(false);
    expect(changes.removedNodes).toEqual([{ id: "p", actor: bob }]);
    expect(changes.removedEdges).toEqual([
      { id: "e1", source: "a", target: "b", actor: bob },
      { id: "e2", source: null, target: null, actor: alice },
    ]);
  });

  it("leaves out connections removed along with a deleted node", () => {
    const changes = changesFrom(
      [
        recorded(bob, { type: "delete_nodes", ids: ["p"] }),
        recorded(bob, { type: "delete_edges", ids: ["e1"] }),
      ],
      () => ({ source: "p", target: "b" }),
    );

    expect(changes.removedNodes.map((node) => node.id)).toEqual(["p"]);
    expect(changes.removedEdges).toEqual([]);
  });

  it("treats something deleted and added back as added", () => {
    const changes = changesFrom([
      recorded(alice, { type: "delete_edges", ids: ["e1"] }),
      recorded(alice, { type: "delete_nodes", ids: ["a"] }),
      recorded(bob, {
        type: "add_edges",
        edges: [{ id: "e1", source: "x", target: "y" }],
      }),
      recorded(bob, { type: "add_nodes", nodes: [{ id: "a" }] }),
    ]);

    expect(changes.removedEdges).toEqual([]);
    expect(changes.removedNodes).toEqual([]);
    expect(changes.edges.get("e1")).toEqual(bob);
    expect(changes.nodes.get("a")).toMatchObject({ actor: bob, added: true });
  });

  it("credits a connection's own changes and a table's cells to whoever made them", () => {
    const changes = changesFrom([
      recorded(alice, {
        type: "add_edges",
        edges: [{ id: "e1", source: "a", target: "b" }],
      }),
      recorded(bob, {
        type: "update_edges",
        updates: [
          {
            id: "e1",
            op: "set_field",
            path: ["data", "targetHandle", "inputTypes"],
            value: ["Data"],
          },
        ],
      }),
      recorded(bob, {
        type: "update_nodes",
        updates: [
          {
            id: "a",
            op: "set_field",
            path: [
              "data",
              "node",
              "template",
              "headers",
              "value",
              { id: "r1" },
              "v",
            ],
            value: "x",
          },
          {
            id: "a",
            op: "set_field",
            path: ["data", "node", "outputs", { key: "text" }, "hidden"],
            value: true,
          },
        ],
      }),
    ]);

    expect(changes.edges.get("e1")).toEqual(bob);
    expect(Object.fromEntries(changes.nodes.get("a")!.fields)).toEqual({
      headers: bob,
    });
    expect(changes.nodes.get("a")!.operations).toHaveLength(1);
  });

  it("ignores flow settings and empty input", () => {
    const changes = changesFrom([
      recorded(alice, { type: "update_metadata", name: "Renamed" }),
    ]);
    expect(changes.nodes.size).toBe(0);
    expect(changes.edges.size).toBe(0);
    expect(changes.removedNodes).toEqual([]);
    expect(changesFrom([]).nodes.size).toBe(0);
  });
});

describe("operationsAt", () => {
  const node = (id: string) => ({
    id,
    position: { x: 0, y: 0 },
    data: { node: { template: { text: { value: "" } } } },
  });
  const base: FlowGraph = { nodes: [node("a"), node("b")], edges: [] };

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

  function timeline() {
    const first = entry([
      recorded(alice, {
        type: "update_nodes",
        updates: [setField("a", "text")],
      }),
      recorded(bob, { type: "update_nodes", updates: [setField("b", "text")] }),
    ]);
    const second = entry([
      recorded(bob, { type: "update_nodes", updates: [move("a")] }),
    ]);
    return buildHistoryTimeline({
      flowId: "f",
      baseRevision: 0,
      base,
      entries: [first, second],
    });
  }

  const revisionsAt = (history: ReturnType<typeof timeline>, at: number) =>
    operationsAt(history, at).map((op) => op.revision);

  it("returns the whole entry at an entry's end", () => {
    const history = timeline();
    expect(revisionsAt(history, 2)).toEqual([1, 2]);
    expect(revisionsAt(history, 3)).toEqual([3]);
  });

  it("returns the one operation inside an entry, and none at the base", () => {
    const history = timeline();
    expect(revisionsAt(history, 1)).toEqual([1]);
    expect(revisionsAt(history, 0)).toEqual([]);
  });

  it("gives every caller the same changes for a revision", () => {
    const history = timeline();
    const changes = changesAt(history, 2);
    expect(changesAt(history, 2)).toBe(changes);
    expect([...changes.nodes.keys()]).toEqual(["a", "b"]);
    expect(changes.nodes.get("a")?.actor).toEqual(alice);
    expect(changesAt(history, 1).nodes.has("b")).toBe(false);
  });
});

describe("groupByActor", () => {
  it("merges consecutive operations by the same person", () => {
    const ops = [
      recorded(alice, { type: "update_nodes", updates: [move("a")] }),
      recorded(alice, { type: "update_nodes", updates: [move("a")] }),
      recorded(bob, { type: "update_nodes", updates: [move("a")] }),
      recorded(alice, { type: "update_nodes", updates: [move("a")] }),
    ];
    expect(
      groupByActor(ops).map((group) => [
        group.actor.username,
        group.operations.map((op) => op.revision),
      ]),
    ).toEqual([
      ["alice", [1, 2]],
      ["bob", [3]],
      ["alice", [4]],
    ]);
  });
});
