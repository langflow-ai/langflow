// Generate the shared fixtures whose expected outputs come from the editor's engine.
//
// Inverses, the editor's table helpers (which renumber a table when a gap has
// no room left) and the edge fixes a restore sends exist only in the editor's
// TypeScript engine, so their expected outputs come from it, never from the
// Rust engine. Bundle the TypeScript engine at the reference commit
// (ad19da0df4, oplog-history-ui) into one CommonJS file that exports
// applyFlowOperations, graphsEqual, edgeFixes, fixesForEdges,
// withTableRowIds, withNodesTableRowIds and appendTableRows, then run:
//
//     node src/lfx-native/fixtures/tools/generate_editor.mjs <bundle.cjs>
//
// It rewrites inverse_cases.json and editor_cases.json. Row ids the editor
// draws at random are stored as "<generated row id>".

import { createRequire } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const engine = createRequire(import.meta.url)(resolve(process.argv[2]));
const fixtures = join(dirname(fileURLToPath(import.meta.url)), "..");
const REFERENCE = "the editor's engine at ad19da0df4 (oplog-history-ui)";
const GENERATED_ROW_ID = "<generated row id>";
const LINE_WIDTH = 160;

// --- The fixture layout of fixture_json.py ----------------------------------------------

function inlineJson(value) {
  // Python's json.dumps with separators (", ", ": "), applied to every value.
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(inlineJson).join(", ")}]`;
  return `{${Object.entries(value)
    .map(([key, item]) => `${JSON.stringify(key)}: ${inlineJson(item)}`)
    .join(", ")}}`;
}

function dump(value, indent, used) {
  const flat = inlineJson(value);
  const container = value !== null && typeof value === "object";
  const empty = container && Object.keys(value).length === 0;
  if (!container || empty || indent + used + [...flat].length <= LINE_WIDTH) return flat;
  const pad = " ".repeat(indent + 2);
  if (Array.isArray(value)) {
    const items = value.map((item) => pad + dump(item, indent + 2, 0));
    return `[\n${items.join(",\n")}\n${" ".repeat(indent)}]`;
  }
  const items = Object.entries(value).map(([key, item]) => {
    const prefix = `${JSON.stringify(key)}: `;
    return pad + prefix + dump(item, indent + 2, [...prefix].length);
  });
  return `{\n${items.join(",\n")}\n${" ".repeat(indent)}}`;
}

function write(name, document) {
  writeFileSync(join(fixtures, name), `${dump(document, 0, 0)}\n`);
}


const clone = (value) => JSON.parse(JSON.stringify(value));

// --- inverse_cases.json ------------------------------------------------------------------

const handle = (value) => JSON.stringify(value).replaceAll('"', "œ");

function edge(id, source, target, output, input) {
  const sourceHandle = { name: output };
  const targetHandle = input;
  return {
    id,
    source,
    target,
    sourceHandle: handle(sourceHandle),
    targetHandle: handle(targetHandle),
    data: { sourceHandle, targetHandle },
  };
}

function inverseBase() {
  return {
    name: "flow",
    nodes: [
      {
        id: "a",
        data: {
          node: {
            template: { text: { type: "str", value: "hi" } },
            outputs: [{ name: "out" }, { name: "mid" }, { name: "last" }, { name: "loop", allows_loop: true }],
          },
        },
      },
      {
        id: "b",
        data: {
          node: {
            template: {
              f: { type: "str", value: "x" },
              many: { type: "str", list: true, value: [] },
              rows: {
                type: "table",
                value: [
                  { _id: "r1", _pos: 1, k: "one" },
                  { _id: "r2", _pos: 2, k: "two" },
                  { _id: "r3", _pos: 3, k: "three" },
                ],
              },
            },
            outputs: [],
          },
        },
      },
    ],
    edges: [
      edge("e1", "a", "b", "out", { fieldName: "f" }),
      edge("e2", "a", "b", "mid", { fieldName: "many" }),
      edge("loop", "a", "a", "out", { name: "loop" }),
    ],
  };
}

const node = (id, updates) => ({ type: "update_nodes", updates: updates.map((update) => ({ id, ...update })) });
const set = (path, value, extra = {}) => ({ op: "set_field", path, value, ...extra });
const del = (path) => ({ op: "delete_field", path });
const OUTPUTS = ["data", "node", "outputs"];
const TEMPLATE = ["data", "node", "template"];

const INVERSE_CASES = [
  ["deleting a node puts it and its edges back", [{ type: "delete_nodes", ids: ["b"] }]],
  ["deleting edges puts them back", [{ type: "delete_edges", ids: ["e1", "loop", "missing"] }]],
  ["adding a node is undone by deleting it", [{ type: "add_nodes", nodes: [{ id: "c", data: { node: { template: {} } } }] }]],
  ["adding an edge is undone by deleting it", [{ type: "add_edges", edges: [edge("e3", "a", "b", "last", { fieldName: "many" })] }]],
  ["a set of an existing value puts the value back", [node("b", [set([...TEMPLATE, "f", "value"], "y")])]],
  ["a set of a new key is undone by deleting it", [node("b", [set([...TEMPLATE, "f", "info"], "help")])]],
  ["a type change is undone with from_type", [node("b", [set([...TEMPLATE, "f", "value"], 5, { from_type: "string" })])]],
  ["a delete of an existing key puts it back", [node("b", [del([...TEMPLATE, "f", "type"])])]],
  ["a delete that finds nothing has no inverse", [node("b", [del([...TEMPLATE, "f", "missing"])])]],
  ["deleting a field puts back the edges into it", [node("b", [del([...TEMPLATE, "f"])])]],
  ["deleting the last output is undone by a selector write", [node("a", [del([...OUTPUTS, { key: "loop" }])])]],
  ["deleting an output that is not last writes the list back", [node("a", [del([...OUTPUTS, { key: "mid" }])])]],
  [
    "deleting two outputs that are not last splits the inverse",
    [node("a", [del([...OUTPUTS, { key: "out" }]), del([...OUTPUTS, { key: "mid" }])])],
  ],
  ["replacing the outputs puts back the list and its edges", [node("a", [set(OUTPUTS, [{ name: "out" }])])]],
  ["adding a table row is undone by deleting it", [node("b", [set([...TEMPLATE, "rows", "value", { id: "r4" }], { _id: "r4", _pos: 4, k: "four" })])]],
  ["deleting a table row puts it back", [node("b", [del([...TEMPLATE, "rows", "value", { id: "r1" }])])]],
  ["moving a table row puts its position back", [node("b", [set([...TEMPLATE, "rows", "value", { id: "r3" }, "_pos"], 0.5)])]],
  [
    "two writes of one path in one batch undo in order",
    [node("b", [set([...TEMPLATE, "f", "value"], "y")]), node("b", [set([...TEMPLATE, "f", "value"], "z")])],
  ],
  ["metadata sets and deletes are undone", [{ type: "update_metadata", fields: { name: "renamed", added: 1 }, delete_keys: ["name", "absent"] }]],
  [
    "rewiring an edge's handles puts them back",
    [
      {
        type: "update_edges",
        updates: [
          { id: "e1", op: "set_field", path: ["targetHandle"], value: handle({ fieldName: "many" }) },
          { id: "e1", op: "set_field", path: ["data", "targetHandle"], value: { fieldName: "many" } },
        ],
      },
    ],
  ],
  ["a batch of several operations", [{ type: "delete_edges", ids: ["e2"] }, node("a", [del([...OUTPUTS, { key: "mid" }])]), { type: "delete_nodes", ids: ["b"] }]],
];

function inverseCase(name, base, operations) {
  const result = engine.applyFlowOperations(clone(base), clone(operations), { inverse: true });
  let graph = result.flowData;
  for (const inverse of [...result.inverseOperations].reverse()) {
    graph = engine.applyFlowOperations(graph, clone(inverse), { restoring: true }).flowData;
  }
  if (!engine.graphsEqual(graph, base)) throw new Error(`the editor's inverses do not restore: ${name}`);
  return { name, base, operations, inverse: result.inverseOperations };
}

function inverseCases() {
  const cases = [];
  const golden = JSON.parse(readFileSync(join(fixtures, "apply_cases.json"), "utf8"));
  for (const c of golden.cases) {
    if (c.error) continue;
    cases.push(inverseCase(`apply case: ${c.name}`, c.base, c.operations));
  }
  for (const [name, operations] of INVERSE_CASES) cases.push(inverseCase(name, inverseBase(), operations));
  return {
    description:
      `Inverses: what undoes each operation of a batch. Expected outputs come from ${REFERENCE}. ` +
      "Applying `operations` to `base` with inverses on gives `inverse`, one list per operation. Applying those " +
      "lists last first, each in a call of its own with `restoring` set, gives back `base`. Ids a delete names " +
      "and the entries an add lists compare as sets keyed by id; numbers compare by value.",
    cases,
  };
}

// --- editor_cases.json ---------------------------------------------------------------------

function placeholders(value, known) {
  if (Array.isArray(value)) return value.map((item) => placeholders(item, known));
  if (value === null || typeof value !== "object") return value;
  const out = {};
  for (const [key, item] of Object.entries(value)) {
    out[key] = key === "_id" && typeof item === "string" && !known.has(item) ? GENERATED_ROW_ID : placeholders(item, known);
  }
  return out;
}

function ids(...values) {
  const known = new Set();
  const visit = (value) => {
    if (Array.isArray(value)) value.forEach(visit);
    else if (value !== null && typeof value === "object") {
      for (const [key, item] of Object.entries(value)) {
        if (key === "_id" && typeof item === "string") known.add(item);
        visit(item);
      }
    }
  };
  values.forEach(visit);
  return known;
}

const LEGACY = [
  { key: "Accept", value: "json" },
  { key: "Auth", value: "token" },
];
const KEYED = [
  { _id: "r1", _pos: 1, key: "Accept", value: "json" },
  { _id: "r2", _pos: 2, key: "Auth", value: "token" },
];

const ASSIGN_CASES = [
  ["rows that have ids and positions are left as they are", KEYED, undefined],
  ["new rows get random ids and positions in order", LEGACY, undefined],
  ["a row equal to a previous row takes its id and position", LEGACY, KEYED],
  ["a run between two positions is spread evenly", [{ _id: "a", _pos: 1 }, { k: 1 }, { k: 2 }, { _id: "b", _pos: 2 }], undefined],
  ["a gap with no room left renumbers the table in stored order", [{ _id: "a", _pos: 1 }, { k: 1 }, { _id: "b", _pos: 1 + 2 ** -52 }], undefined],
  ["a run before the first position counts down", [{ k: 1 }, { k: 2 }, { _id: "a", _pos: 10 }], undefined],
  ["a run between out-of-order neighbours follows the one before", [{ _id: "a", _pos: 3 }, { k: 1 }, { _id: "b", _pos: 1 }], undefined],
  ["a duplicate id is replaced", [{ _id: "a", _pos: 1 }, { _id: "a", _pos: 2 }], undefined],
  ["a table with a row that is not an object is left alone", [LEGACY[0], "x"], undefined],
];

const APPEND_CASES = [
  ["rows are appended one past the last position", KEYED, [{ key: "New", value: "x" }]],
  ["a duplicated row gets a new id and position", KEYED, [KEYED[0], KEYED[1]]],
  ["the next position follows a fractional last position", [{ _id: "a", _pos: 2.5 }], [{ k: 1 }, { k: 2 }]],
  ["a table without ids gets them first", LEGACY, [{ key: "New" }]],
  ["the first row of an empty table is 1", [], [{ key: "New" }]],
];

function tableNode(id, rows) {
  return {
    id,
    data: {
      node: {
        template: {
          headers: { type: "table", _input_type: "TableInput", value: rows },
          url: { type: "str", value: "http://x" },
        },
      },
    },
  };
}

const NODES_CASES = [
  ["a new node gets ids on every table", [tableNode("api", LEGACY)], []],
  ["an unchanged legacy table is left alone", [tableNode("api", LEGACY)], [tableNode("api", LEGACY)]],
  ["a changed table keeps the ids of rows it still holds", [tableNode("api", [...LEGACY, { key: "New" }])], [tableNode("api", KEYED)]],
];

function editorEdge(id, extra = {}) {
  return { ...edge(id, "a", "b", "out", { fieldName: "f" }), ...extra };
}

const EDGE_FIX_CASES = [
  ["an edge the preview dropped is deleted", [editorEdge("e1"), editorEdge("e2")], [editorEdge("e1")]],
  [
    "a handle the preview respelled is rewritten in both forms",
    [editorEdge("e1", { targetHandle: "{œfieldNameœ: œfœ}" })],
    [editorEdge("e1", { targetHandle: handle({ fieldName: "g" }), data: { sourceHandle: { name: "out" }, targetHandle: { fieldName: "g" } } })],
  ],
  ["an edge without data gets its handles as data", [{ ...editorEdge("e1"), data: undefined }], [editorEdge("e1")]],
  ["an edge whose data is null gets its handles as data", [{ ...editorEdge("e1"), data: null }], [editorEdge("e1")]],
  ["nothing changed, nothing to fix", [editorEdge("e1")], [editorEdge("e1")]],
];

const FIXES_FOR_EDGES = [
  {
    name: "only the fixes of the flagged edges are kept",
    fixes: [
      { type: "delete_edges", ids: ["e1", "e2"] },
      {
        type: "update_edges",
        updates: [
          { id: "e2", op: "set_field", path: ["targetHandle"], value: "x" },
          { id: "e3", op: "set_field", path: ["targetHandle"], value: "y" },
        ],
      },
    ],
    edge_ids: ["e2"],
  },
  { name: "fixes for no flagged edge are dropped", fixes: [{ type: "delete_edges", ids: ["e1"] }], edge_ids: ["e9"] },
];

function editorCases() {
  return {
    description:
      `The editor's side of table rows and restore fixes. Expected outputs come from ${REFERENCE}. ` +
      "`assign` gives rows the ids and positions the editor writes (withTableRowIds): unlike the server, it " +
      "renumbers a table 1..n in stored order when a gap has no room left. `append` adds rows after a table " +
      "(appendTableRows). `assign_nodes` gives row ids to the tables nodes add or change against the same nodes " +
      "as they were (withNodesTableRowIds). `edge_fixes` turns a revision's edges as read into the edges its " +
      "preview shows (edgeFixes); `fixes_for_edges` keeps the fixes of the flagged edges (fixesForEdges). " +
      `Random row ids appear as \`${GENERATED_ROW_ID}\`; positions compare by value.`,
    assign: ASSIGN_CASES.map(([name, rows, previous]) => ({
      name,
      rows,
      ...(previous ? { previous } : {}),
      expected: placeholders(engine.withTableRowIds(clone(rows), previous && clone(previous)), ids(rows, previous)),
    })),
    append: APPEND_CASES.map(([name, rows, newRows]) => ({
      name,
      rows,
      new_rows: newRows,
      expected: placeholders(engine.appendTableRows(clone(rows), clone(newRows)), ids(rows)),
    })),
    assign_nodes: NODES_CASES.map(([name, nodes, previous]) => ({
      name,
      nodes,
      previous,
      expected: placeholders(engine.withNodesTableRowIds(clone(nodes), clone(previous)), ids(nodes, previous)),
    })),
    edge_fixes: EDGE_FIX_CASES.map(([name, read, shown]) => ({
      name,
      read: clone(read),
      shown: clone(shown),
      fixes: clone(engine.edgeFixes(clone(read), clone(shown))),
    })),
    fixes_for_edges: FIXES_FOR_EDGES.map((c) => ({
      ...c,
      expected: engine.fixesForEdges(clone(c.fixes), new Set(c.edge_ids)),
    })),
  };
}

write("inverse_cases.json", inverseCases());
console.log("wrote inverse_cases.json");
write("editor_cases.json", editorCases());
console.log("wrote editor_cases.json");
