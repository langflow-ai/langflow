import {
  appendTableRows,
  hasTableRowIds,
  isTableField,
  stripTableRowIds,
  stripTableRowIdsFromGraph,
  withNodesTableRowIds,
  withNodeTableRowIds,
  withTableRowIds,
  withTemplateTableRowIds,
} from "../table-row-ids";

type Row = Record<string, unknown>;

const ids = (rows: Row[]) => rows.map((row) => row._id);
const positions = (rows: Row[]) => rows.map((row) => row._pos as string);

function expectSorted(rows: Row[]) {
  const pos = positions(rows);
  expect([...pos].sort()).toEqual(pos);
  expect(new Set(pos).size).toBe(pos.length);
}

const tableField = (value: unknown) => ({
  type: "table",
  _input_type: "TableInput",
  table_schema: { columns: [{ name: "key" }, { name: "value" }] },
  value,
});

const node = (id: string, template: Record<string, unknown>) => ({
  id,
  type: "genericNode",
  data: { id, type: "APIRequest", node: { template } },
});

describe("isTableField", () => {
  it("knows a table by its type or its input class", () => {
    expect(isTableField({ type: "table" })).toBe(true);
    expect(isTableField({ type: "other", _input_type: "TableInput" })).toBe(
      true,
    );
    expect(isTableField({ type: "str" })).toBe(false);
    expect(isTableField(null)).toBe(false);
  });
});

describe("withTableRowIds", () => {
  it("gives a legacy table ids and positions in its current order", () => {
    const rows = [{ key: "a" }, { key: "b" }, { key: "c" }];

    const result = withTableRowIds(rows);

    expect(result.map((row) => row.key)).toEqual(["a", "b", "c"]);
    expect(positions(result)).toEqual(["a0", "a1", "a2"]);
    expect(new Set(ids(result)).size).toBe(3);
    expect(ids(result).every((id) => typeof id === "string")).toBe(true);
    expect(hasTableRowIds(result)).toBe(true);
    // The input is left as it was.
    expect(rows[0]).toEqual({ key: "a" });
  });

  it("returns a table that already has ids unchanged", () => {
    const rows = [
      { _id: "r1", _pos: "a0", key: "a" },
      { _id: "r2", _pos: "a1", key: "b" },
    ];

    expect(withTableRowIds(rows)).toBe(rows);
  });

  it("places new rows between the rows around them", () => {
    const rows = [
      { _id: "r1", _pos: "a0", key: "a" },
      { key: "new" },
      { _id: "r2", _pos: "a1", key: "b" },
      { key: "last" },
    ];

    const result = withTableRowIds(rows);

    expect(result.map((row) => row.key)).toEqual(["a", "new", "b", "last"]);
    expect(result[0]._pos).toBe("a0");
    expect(result[2]._pos).toBe("a1");
    const middle = result[1]._pos as string;
    expect(middle > "a0" && middle < "a1").toBe(true);
    expectSorted(result);
  });

  it("gives a duplicated id a new one", () => {
    const rows = [
      { _id: "r1", _pos: "a0", key: "a" },
      { _id: "r1", _pos: "a0", key: "a" },
    ];

    const result = withTableRowIds(rows);

    expect(result[0]._id).toBe("r1");
    expect(result[1]._id).not.toBe("r1");
    expect(hasTableRowIds(result)).toBe(true);
  });

  it("re-places a row whose position no longer fits its place", () => {
    const rows = [
      { _id: "r2", _pos: "a5", key: "b" },
      { _id: "r1", _pos: "a1", key: "a" },
    ];

    const result = withTableRowIds(rows);

    expect(result.map((row) => row.key)).toEqual(["b", "a"]);
    expect(result[0]._pos).toBe("a5");
    expect(result[1]._pos > "a5").toBe(true);
    expect(ids(result)).toEqual(["r2", "r1"]);
  });

  it("gives an invalid position a valid one", () => {
    const result = withTableRowIds([{ _id: "r1", _pos: "nope!", key: "a" }]);

    expect(result[0]).toEqual({ _id: "r1", _pos: "a0", key: "a" });
  });

  it("keeps the ids of rows a refresh returned without them", () => {
    const previous = [
      { _id: "r1", _pos: "a0", key: "a", value: "1" },
      { _id: "r2", _pos: "a1", key: "b", value: "2" },
    ];
    const refreshed: Row[] = [
      { key: "a", value: "1" },
      { key: "b", value: "changed" },
    ];

    const result = withTableRowIds(refreshed, previous);

    expect(result[0]).toEqual({ _id: "r1", _pos: "a0", key: "a", value: "1" });
    expect(result[1]._id).not.toBe("r2");
    expect(result[1].value).toBe("changed");
    expectSorted(result);
  });

  it("leaves rows that are not objects alone", () => {
    const rows = ["a", "b"];

    expect(withTableRowIds(rows)).toBe(rows);
  });
});

describe("appendTableRows", () => {
  it("appends rows with new ids after the last row", () => {
    const rows = [{ _id: "r1", _pos: "a0", key: "a" }];

    const result = appendTableRows(rows, [
      { _id: "r1", _pos: "a0", key: "copy" },
      { key: "new" },
    ]);

    expect(result.map((row) => row.key)).toEqual(["a", "copy", "new"]);
    expect(result[0]).toBe(rows[0]);
    expect(new Set(ids(result)).size).toBe(3);
    expect(positions(result)).toEqual(["a0", "a1", "a2"]);
  });

  it("gives a legacy table ids before appending", () => {
    const result = appendTableRows([{ key: "a" }], [{ key: "b" }]);

    expect(hasTableRowIds(result)).toBe(true);
    expect(result.map((row) => row.key)).toEqual(["a", "b"]);
  });
});

describe("withTemplateTableRowIds", () => {
  it("leaves an unchanged legacy table as it is", () => {
    const template = { headers: tableField([{ key: "a" }]) };
    const previous = { headers: tableField([{ key: "a" }]) };

    expect(withTemplateTableRowIds(template, previous)).toBe(template);
  });

  it("gives a changed table ids, writing it whole", () => {
    const template = {
      headers: tableField([{ key: "a" }, { key: "b" }]),
      url: { type: "str", value: "x" },
    };
    const previous = { headers: tableField([{ key: "a" }]) };

    const result = withTemplateTableRowIds(template, previous);

    expect(result).not.toBe(template);
    expect(hasTableRowIds(result.headers.value as unknown[])).toBe(true);
    expect(result.url).toBe(template.url);
  });

  it("gives every table of a new template ids", () => {
    const template = { headers: tableField([{ key: "a" }]) };

    const result = withTemplateTableRowIds(template);

    expect(hasTableRowIds(result.headers.value as unknown[])).toBe(true);
  });

  it("ignores values that are not tables", () => {
    const template = { items: { type: "str", list: true, value: [{ a: 1 }] } };

    expect(withTemplateTableRowIds(template)).toBe(template);
  });
});

describe("withNodesTableRowIds", () => {
  it("gives new nodes' tables ids and leaves untouched nodes alone", () => {
    const existing = node("A", { headers: tableField([{ key: "a" }]) });
    const added = node("B", { headers: tableField([{ key: "default" }]) });

    const result = withNodesTableRowIds([existing, added], [existing]);

    expect(result[0]).toBe(existing);
    expect(
      hasTableRowIds(
        (result[1].data.node.template.headers as { value: unknown[] }).value,
      ),
    ).toBe(true);
  });

  it("returns the same array when nothing changes", () => {
    const nodes = [node("A", { headers: tableField([{ key: "a" }]) })];

    expect(withNodesTableRowIds(nodes, nodes)).toBe(nodes);
  });

  it("leaves nodes without a template alone", () => {
    const note = { id: "note", type: "noteNode", data: { node: {} } };

    expect(withNodeTableRowIds(note)).toBe(note);
  });
});

describe("stripping", () => {
  it("removes row keys from rows", () => {
    expect(
      stripTableRowIds([{ _id: "r1", _pos: "a0", key: "a" }, { key: "b" }]),
    ).toEqual([{ key: "a" }, { key: "b" }]);
  });

  it("removes row keys from every table of a graph, group graphs included", () => {
    const inner = node("inner", {
      rows: tableField([{ _id: "r9", _pos: "a0", key: "x" }]),
    });
    const graph = {
      nodes: [
        node("A", {
          headers: tableField([{ _id: "r1", _pos: "a0", key: "a" }]),
          other: { type: "dict", value: { _id: "kept" } },
        }),
        {
          id: "group",
          data: {
            node: { template: {}, flow: { data: { nodes: [inner] } } },
          },
        },
      ],
    };

    stripTableRowIdsFromGraph(graph);

    const [first] = graph.nodes as ReturnType<typeof node>[];
    expect(first.data.node.template.headers).toMatchObject({
      value: [{ key: "a" }],
    });
    expect(first.data.node.template.other).toEqual({
      type: "dict",
      value: { _id: "kept" },
    });
    expect(inner.data.node.template.rows).toMatchObject({
      value: [{ key: "x" }],
    });
  });
});
