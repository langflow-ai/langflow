import type { AllNodeType, EdgeType } from "@/types/flow";
import {
  applySelectedChanges,
  contestedTargetKeys,
  diffGraphs,
  groupChangesByTarget,
  siblingChangeIds,
} from "../flow-diff";

type FieldSpec = { value: unknown; display_name?: string; password?: boolean };

const node = (
  id: string,
  displayName: string,
  fields: Record<string, FieldSpec> = {},
): AllNodeType =>
  ({
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: {
      id,
      type: "Component",
      node: {
        display_name: displayName,
        description: "",
        documentation: "",
        template: Object.fromEntries(
          Object.entries(fields).map(([name, spec]) => [
            name,
            {
              type: "str",
              required: false,
              list: false,
              show: true,
              readonly: false,
              ...spec,
            },
          ]),
        ),
      },
    },
  }) as unknown as AllNodeType;

const edge = (id: string, source: string, target: string): EdgeType =>
  ({ id, source, target }) as EdgeType;

const graph = (nodes: AllNodeType[], edges: EdgeType[] = []) => ({
  nodes,
  edges,
});

describe("diffGraphs", () => {
  it("should report an added node when one side gained it", () => {
    const base = graph([node("a", "Chat Input")]);
    const next = graph([node("a", "Chat Input"), node("b", "Knowledge Base")]);

    const changes = diffGraphs(base, next);

    expect(changes).toHaveLength(1);
    expect(changes[0]).toMatchObject({
      badge: "added",
      label: "Knowledge Base",
      targetKey: "node:b",
    });
  });

  it("should report a removed node", () => {
    const changes = diffGraphs(
      graph([node("a", "Chat Input"), node("b", "Split Text")]),
      graph([node("a", "Chat Input")]),
    );

    expect(changes).toHaveLength(1);
    expect(changes[0]).toMatchObject({ badge: "removed", targetKey: "node:b" });
  });

  it("should render a short field change inline with both values", () => {
    const changes = diffGraphs(
      graph([node("a", "OpenAI Model", { temperature: { value: 0.7 } })]),
      graph([node("a", "OpenAI Model", { temperature: { value: 0.3 } })]),
    );

    expect(changes[0].sentence).toEqual({
      key: "multiEdit.change.fieldShort",
      params: {
        field: "temperature",
        before: "0.7",
        after: "0.3",
      },
    });
  });

  it("should use the field display name when there is one", () => {
    const changes = diffGraphs(
      graph([
        node("a", "OpenAI Model", {
          temperature: { value: 0.7, display_name: "Temperature" },
        }),
      ]),
      graph([
        node("a", "OpenAI Model", {
          temperature: { value: 0.3, display_name: "Temperature" },
        }),
      ]),
    );

    expect(changes[0].label).toBe("Temperature");
  });

  it("should fall back to the long form when a value is too big to read inline", () => {
    const long = "You are a helpful assistant. ".repeat(10);
    const changes = diffGraphs(
      graph([node("a", "Prompt", { template: { value: "short" } })]),
      graph([node("a", "Prompt", { template: { value: long } })]),
    );

    expect(changes[0].sentence.key).toBe("multiEdit.change.fieldLong");
    expect(changes[0].detail).toEqual({ before: "short", after: long });
  });

  it("should never expose a secret value in the sentence or the raw diff", () => {
    const changes = diffGraphs(
      graph([
        node("a", "OpenAI", { api_key: { value: "sk-old", password: true } }),
      ]),
      graph([
        node("a", "OpenAI", { api_key: { value: "sk-new", password: true } }),
      ]),
    );

    expect(changes).toHaveLength(1);
    expect(changes[0].detail).toBeUndefined();
    expect(JSON.stringify(changes[0])).not.toContain("sk-old");
    expect(JSON.stringify(changes[0])).not.toContain("sk-new");
  });

  it("should describe an added edge by its endpoints", () => {
    const nodes = [node("a", "Split Text"), node("b", "Knowledge Base")];
    const changes = diffGraphs(
      graph(nodes),
      graph(nodes, [edge("e1", "a", "b")]),
    );

    expect(changes[0]).toMatchObject({
      badge: "added",
      targetKey: "edge:e1",
      sentence: {
        key: "multiEdit.change.edgeAdded",
        params: { source: "Split Text", target: "Knowledge Base" },
      },
    });
  });

  it("should report nothing when the graphs match", () => {
    const nodes = [node("a", "Chat Input", { value: { value: "hi" } })];
    expect(diffGraphs(graph(nodes), graph(nodes))).toEqual([]);
  });

  it("should not report a change when only key order differs", () => {
    const changes = diffGraphs(
      graph([node("a", "N", { cfg: { value: { x: 1, y: 2 } } })]),
      graph([node("a", "N", { cfg: { value: { y: 2, x: 1 } } })]),
    );

    expect(changes).toEqual([]);
  });

  it("should treat a missing graph as empty rather than throwing", () => {
    expect(diffGraphs(null, graph([node("a", "N")]))).toHaveLength(1);
    expect(diffGraphs(graph([node("a", "N")]), null)).toHaveLength(1);
  });
});

describe("contestedTargetKeys", () => {
  it("should mark a component both people changed as contested", () => {
    const mine = diffGraphs(
      graph([node("a", "Prompt", { template: { value: "base" } })]),
      graph([node("a", "Prompt", { template: { value: "mine" } })]),
    );
    const theirs = diffGraphs(
      graph([node("a", "Prompt", { template: { value: "base" } })]),
      graph([node("a", "Prompt", { template: { value: "theirs" } })]),
    );

    expect(contestedTargetKeys(mine, theirs)).toEqual(new Set(["node:a"]));
  });

  it("should not contest components only they touched", () => {
    const mine = diffGraphs(
      graph([node("a", "Prompt", { t: { value: "1" } })]),
      graph([node("a", "Prompt", { t: { value: "2" } })]),
    );
    const theirs = diffGraphs(
      graph([node("b", "Model", { t: { value: "1" } })]),
      graph([node("b", "Model", { t: { value: "2" } })]),
    );

    expect(contestedTargetKeys(mine, theirs).size).toBe(0);
  });
});

describe("applySelectedChanges", () => {
  const base = graph([node("a", "Prompt", { t: { value: "base" } })]);

  it("should keep my graph untouched when nothing is selected", () => {
    const mine = graph([node("a", "Prompt", { t: { value: "mine" } })]);
    const theirs = graph([
      node("a", "Prompt", { t: { value: "base" } }),
      node("b", "New", {}),
    ]);
    const changes = diffGraphs(base, theirs);

    const result = applySelectedChanges(mine, theirs, changes, new Set());

    expect(result.nodes).toHaveLength(1);
    expect(result.nodes[0].data.node?.template?.t?.value).toBe("mine");
  });

  it("should adopt only the selected change", () => {
    const mine = graph([node("a", "Prompt", { t: { value: "mine" } })]);
    const theirs = graph([
      node("a", "Prompt", { t: { value: "base" } }),
      node("b", "Knowledge Base", {}),
      node("c", "Other", {}),
    ]);
    const changes = diffGraphs(base, theirs);
    const addB = changes.find((c) => c.targetKey === "node:b")!;

    const result = applySelectedChanges(
      mine,
      theirs,
      changes,
      new Set([addB.id]),
    );

    const ids = result.nodes.map((n) => n.id).sort();
    expect(ids).toEqual(["a", "b"]);
    expect(
      result.nodes.find((n) => n.id === "a")?.data.node?.template?.t?.value,
    ).toBe("mine");
  });

  it("should apply a removal they made when it is selected", () => {
    const mine = graph([node("a", "Prompt", {}), node("b", "Doomed", {})]);
    const theirs = graph([node("a", "Prompt", {})]);
    const changes = diffGraphs(
      graph([node("a", "Prompt", {}), node("b", "Doomed", {})]),
      theirs,
    );

    const result = applySelectedChanges(
      mine,
      theirs,
      changes,
      new Set(changes.map((c) => c.id)),
    );

    expect(result.nodes.map((n) => n.id)).toEqual(["a"]);
  });

  it("should bring the node an adopted edge needs, so the tick is not a no-op", () => {
    const mine = graph([node("a", "A", {})]);
    const theirs = graph(
      [node("a", "A", {}), node("b", "B", {})],
      [edge("e1", "a", "b")],
    );
    const changes = diffGraphs(graph([node("a", "A", {})]), theirs);
    const edgeChange = changes.find((c) => c.targetKey === "edge:e1")!;

    const result = applySelectedChanges(
      mine,
      theirs,
      changes,
      new Set([edgeChange.id]),
    );

    expect(result.edges.map((e) => e.id)).toEqual(["e1"]);
    expect(result.nodes.map((n) => n.id)).toEqual(["a", "b"]);
  });

  it("should keep an adopted edge when its endpoints are adopted too", () => {
    const mine = graph([node("a", "A", {})]);
    const theirs = graph(
      [node("a", "A", {}), node("b", "B", {})],
      [edge("e1", "a", "b")],
    );
    const changes = diffGraphs(graph([node("a", "A", {})]), theirs);

    const result = applySelectedChanges(
      mine,
      theirs,
      changes,
      new Set(changes.map((c) => c.id)),
    );

    expect(result.edges.map((e) => e.id)).toEqual(["e1"]);
  });
});

describe("layout changes", () => {
  const at = (id: string, x: number, y: number): AllNodeType =>
    ({ ...node(id, "Prompt"), position: { x, y } }) as AllNodeType;

  it("should report a node the user only moved", () => {
    const changes = diffGraphs(
      graph([at("a", 0, 0)]),
      graph([at("a", 120, 80)]),
    );

    expect(changes).toHaveLength(1);
    expect(changes[0]).toMatchObject({
      targetKey: "node:a",
      badge: "modified",
      sentence: { key: "multiEdit.change.nodeMoved" },
    });
  });

  it("should ignore sub-pixel drift so a redraw is not a change", () => {
    const changes = diffGraphs(
      graph([at("a", 10, 10)]),
      graph([at("a", 10.2, 9.8)]),
    );

    expect(changes).toEqual([]);
  });
});

describe("siblingChangeIds", () => {
  it("should group every change that belongs to one component", () => {
    const changes = diffGraphs(
      graph([
        node("a", "Model", { temp: { value: "1" }, top_p: { value: "2" } }),
      ]),
      graph([
        node("a", "Model", { temp: { value: "9" }, top_p: { value: "8" } }),
      ]),
    );

    expect(siblingChangeIds(changes, "node:a").sort()).toEqual(
      changes.map((c) => c.id).sort(),
    );
  });

  it("should not group changes from other components", () => {
    const changes = diffGraphs(
      graph([
        node("a", "A", { t: { value: "1" } }),
        node("b", "B", { t: { value: "1" } }),
      ]),
      graph([
        node("a", "A", { t: { value: "2" } }),
        node("b", "B", { t: { value: "2" } }),
      ]),
    );

    expect(siblingChangeIds(changes, "node:a")).toHaveLength(1);
  });
});

describe("choosing their version of a contested component", () => {
  it("should replace my whole component with theirs", () => {
    const base = graph([node("a", "Prompt", { t: { value: "base" } })]);
    const mine = graph([node("a", "Prompt", { t: { value: "mine" } })]);
    const theirs = graph([node("a", "Prompt", { t: { value: "theirs" } })]);
    const theirChanges = diffGraphs(base, theirs);

    const result = applySelectedChanges(
      mine,
      theirs,
      theirChanges,
      new Set(theirChanges.map((c) => c.id)),
    );

    expect(result.nodes[0].data.node?.template?.t?.value).toBe("theirs");
  });

  it("should keep my version when I take nothing of theirs", () => {
    const base = graph([node("a", "Prompt", { t: { value: "base" } })]);
    const mine = graph([node("a", "Prompt", { t: { value: "mine" } })]);
    const theirs = graph([node("a", "Prompt", { t: { value: "theirs" } })]);

    const result = applySelectedChanges(
      mine,
      theirs,
      diffGraphs(base, theirs),
      new Set(),
    );

    expect(result.nodes[0].data.node?.template?.t?.value).toBe("mine");
  });
});

describe("values that are not plain strings", () => {
  const model = (name: string, provider: string) => [
    { id: `${provider}/${name}`, name, provider, icon: "Bot", metadata: {} },
  ];

  it("should detect a model swap stored as an array of objects", () => {
    const changes = diffGraphs(
      graph([
        node("a", "Agent", { model: { value: model("gpt-5.4", "OpenAI") } }),
      ]),
      graph([
        node("a", "Agent", {
          model: { value: model("claude-sonnet-5", "Anthropic") },
        }),
      ]),
    );

    expect(changes).toHaveLength(1);
    expect(changes[0].detail?.after).toContain("claude-sonnet-5");
  });

  it("should not report a change when only object key order differs inside an array", () => {
    const changes = diffGraphs(
      graph([
        node("a", "Agent", {
          model: { value: [{ name: "x", provider: "y" }] },
        }),
      ]),
      graph([
        node("a", "Agent", {
          model: { value: [{ provider: "y", name: "x" }] },
        }),
      ]),
    );

    expect(changes).toEqual([]);
  });

  it("should treat a reordered array as a real change", () => {
    const changes = diffGraphs(
      graph([node("a", "N", { list: { value: ["one", "two"] } })]),
      graph([node("a", "N", { list: { value: ["two", "one"] } })]),
    );

    expect(changes).toHaveLength(1);
  });
});

describe("targets whose id contains the key separator", () => {
  // A real Langflow edge id: it embeds serialized handles, colons included.
  const REAL_EDGE_ID =
    "reactflow__edge-ChatInput-tKQ4d{œdataTypeœ:œChatInputœ,œidœ:œChatInput-tKQ4dœ}-Agent-EXpSZ{œfieldNameœ:œinput_valueœ}";

  it("should apply a selected edge whose id contains colons", () => {
    const nodes = [node("a", "Chat Input"), node("b", "Agent")];
    const base = graph(nodes);
    const theirs = graph(nodes, [
      { id: REAL_EDGE_ID, source: "a", target: "b" } as EdgeType,
    ]);
    const changes = diffGraphs(base, theirs);

    const result = applySelectedChanges(
      base,
      theirs,
      changes,
      new Set(changes.map((c) => c.id)),
    );

    expect(result.edges.map((e) => e.id)).toEqual([REAL_EDGE_ID]);
  });

  it("should remove a selected edge whose id contains colons", () => {
    const nodes = [node("a", "Chat Input"), node("b", "Agent")];
    const withEdge = graph(nodes, [
      { id: REAL_EDGE_ID, source: "a", target: "b" } as EdgeType,
    ]);
    const theirs = graph(nodes);
    const changes = diffGraphs(withEdge, theirs);

    const result = applySelectedChanges(
      withEdge,
      theirs,
      changes,
      new Set(changes.map((c) => c.id)),
    );

    expect(result.edges).toEqual([]);
  });

  it("should carry the target kind and id on every change it emits", () => {
    const changes = diffGraphs(
      graph([node("a", "N", { t: { value: "1" } })]),
      graph(
        [node("a", "N", { t: { value: "2" } }), node("b", "New")],
        [{ id: REAL_EDGE_ID, source: "a", target: "b" } as EdgeType],
      ),
    );

    expect(changes.length).toBeGreaterThan(0);
    for (const change of changes) {
      expect(change.targetKind).toMatch(/^(node|edge)$/);
      expect(change.targetKey).toBe(`${change.targetKind}:${change.targetId}`);
    }
  });
});

describe("groupChangesByTarget", () => {
  it("should put every change to one component under a single heading", () => {
    // The dialog offers a component whole, so two checkboxes for one component
    // promised a choice the merge could not honour.
    const base = graph([node("a", "Chat Input", { text: { value: "one" } })]);
    const theirs = graph([
      {
        ...node("a", "Chat Input", { text: { value: "two" } }),
        position: { x: 90, y: 90 },
      },
    ]);

    const groups = groupChangesByTarget(diffGraphs(base, theirs));

    expect(groups).toHaveLength(1);
    expect(groups[0].targetKey).toBe("node:a");
    expect(groups[0].changes.length).toBeGreaterThan(1);
  });

  it("should name the group after the component, not the last field touched", () => {
    const base = graph([node("a", "Chat Input", { text: { value: "one" } })]);
    const theirs = graph([node("a", "Chat Input", { text: { value: "two" } })]);

    const [group] = groupChangesByTarget(diffGraphs(base, theirs));

    expect(group.label).toBe("Chat Input");
  });

  it("should keep separate components apart", () => {
    const base = graph([node("a", "A", {}), node("b", "B", {})]);
    const theirs = graph([
      { ...node("a", "A", {}), position: { x: 50, y: 50 } },
      { ...node("b", "B", {}), position: { x: 70, y: 70 } },
    ]);

    expect(groupChangesByTarget(diffGraphs(base, theirs))).toHaveLength(2);
  });

  it("should let the strongest badge speak for the component", () => {
    const base = graph([]);
    const theirs = graph([node("a", "A", { text: { value: "x" } })]);

    const [group] = groupChangesByTarget(diffGraphs(base, theirs));

    expect(group.badge).toBe("added");
  });
});

describe("what a reader should not have to wade through", () => {
  it("should read a model selection as its name, not as the object carrying it", () => {
    const picked = [
      {
        name: "claude-fable-5-1",
        provider: "Anthropic",
        icon: "Anthropic",
        metadata: { context_length: 128000 },
      },
    ];
    const base = graph([node("a", "Agent", { model: { value: picked } })]);
    const theirs = graph([node("a", "Agent", { model: { value: [] } })]);

    const [change] = diffGraphs(base, theirs);

    expect(change.sentence.params.before).toBe("claude-fable-5-1");
    expect(change.sentence.params.after).toBe("[]");
    expect(JSON.stringify(change)).not.toContain("context_length");
  });

  it("should never show template metadata as somebody's edit", () => {
    const base = graph([
      node("a", "Agent", {
        _frontend_node_flow_id: { value: "flow-1" },
        f: { value: "one" },
      }),
    ]);
    const theirs = graph([
      node("a", "Agent", {
        _frontend_node_flow_id: { value: "flow-2" },
        f: { value: "one" },
      }),
    ]);

    expect(diffGraphs(base, theirs)).toEqual([]);
  });

  it("should not repeat the component name inside its own group", () => {
    const base = graph([node("a", "Chat Input", { text: { value: "one" } })]);
    const theirs = graph([node("a", "Chat Input", { text: { value: "two" } })]);

    const [group] = groupChangesByTarget(diffGraphs(base, theirs));

    expect(group.label).toBe("Chat Input");
    expect(group.changes[0].sentence.params).not.toHaveProperty("owner");
  });
});

describe("a value that is not there", () => {
  it("should read as a dash rather than leaving a hole in the sentence", () => {
    const base = graph([node("a", "Agent", { model: { value: null } })]);
    const theirs = graph([
      node("a", "Agent", { model: { value: [{ name: "claude-fable-5-1" }] } }),
    ]);

    const [change] = diffGraphs(base, theirs);

    expect(change.sentence.params.before).toBe("—");
    expect(change.sentence.params.after).toBe("claude-fable-5-1");
  });
});
