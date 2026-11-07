// Check the editor's TypeScript engine against the shared fixtures.
//
// The fixture files are the specification of the engine: their expected
// outputs are reviewed data, and every engine must meet them. This script runs
// the editor's engine over the inputs of what only the editor has: inverses
// (inverse_cases.json), and the editor's table rules and edge fixes
// (editor_cases.json). It reports each case whose result differs from the
// expected output, with the case's name and rule. It never writes a fixture
// file. Bundle the TypeScript engine of the stack's top branch
// (oplog-history-ui) into one CommonJS file that exports applyFlowOperations,
// graphsEqual, edgeFixes, fixesForEdges, withTableRowIds, withNodesTableRowIds
// and appendTableRows, then run:
//
//     node src/lfx-native/fixtures/tools/check_editor.mjs <bundle.cjs>
//
// It exits with 1 when a case differs.

import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const engine = createRequire(import.meta.url)(resolve(process.argv[2]));
const fixtures = join(dirname(fileURLToPath(import.meta.url)), "..");
const GENERATED_ROW_ID = "<generated row id>";

const load = (name) => JSON.parse(readFileSync(join(fixtures, name), "utf8"));
const clone = (value) => JSON.parse(JSON.stringify(value));
const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);

class Difference extends Error {
  constructor(what, actual, expected) {
    super(what);
    this.what = what;
    this.actual = actual;
    this.expected = expected;
  }
}

/** Equal as JSON, numbers by value, and a generated row id placeholder matching any row id. */
function matches(actual, expected) {
  if (expected === GENERATED_ROW_ID) return typeof actual === "string" && /^[0-9A-Za-z]{10}$/.test(actual);
  if (Array.isArray(actual) || Array.isArray(expected))
    return Array.isArray(actual) && Array.isArray(expected) && actual.length === expected.length && actual.every((item, i) => matches(item, expected[i]));
  if (isObject(actual) || isObject(expected)) {
    if (!isObject(actual) || !isObject(expected)) return false;
    const keys = Object.keys(actual);
    return keys.length === Object.keys(expected).length && keys.every((key) => key in expected && matches(actual[key], expected[key]));
  }
  return actual === expected;
}

function check(what, actual, expected) {
  // The engine's result as JSON: the fixtures cannot hold an undefined value.
  const value = actual === undefined ? actual : clone(actual);
  if (!matches(value, expected)) throw new Difference(what, value, expected);
}

// --- inverse_cases.json ----------------------------------------------------------------------------

/** Ids a delete names and the entries an add lists, as sets keyed by id. */
function unordered(lists) {
  const keys = { delete_nodes: "ids", delete_edges: "ids", add_nodes: "nodes", add_edges: "edges" };
  const id = (item) => (typeof item === "string" ? item : item.id);
  return lists.map((operations) =>
    operations.map((op) => (keys[op.type] ? { ...op, [keys[op.type]]: [...op[keys[op.type]]].sort((a, b) => (id(a) < id(b) ? -1 : 1)) } : op)),
  );
}

function inverseCase(c) {
  const result = engine.applyFlowOperations(clone(c.base), clone(c.operations), { inverse: true });
  check("inverse operations", unordered(result.inverseOperations), unordered(c.inverse));
  let graph = result.flowData;
  for (const inverse of [...result.inverseOperations].reverse()) {
    graph = engine.applyFlowOperations(graph, clone(inverse), { restoring: true }).flowData;
  }
  if (!engine.graphsEqual(graph, c.base)) throw new Difference("the graph after the inverses", graph, c.base);
}

// --- editor_cases.json -----------------------------------------------------------------------------

const EDITOR_RUNS = {
  assign: (c) => check("rows", engine.withTableRowIds(clone(c.rows), c.previous && clone(c.previous)), c.expected),
  append: (c) => check("rows", engine.appendTableRows(clone(c.rows), clone(c.new_rows)), c.expected),
  assign_nodes: (c) => check("nodes", engine.withNodesTableRowIds(clone(c.nodes), clone(c.previous)), c.expected),
  edge_fixes: (c) => check("fixes", engine.edgeFixes(clone(c.read), clone(c.shown)), c.fixes),
  fixes_for_edges: (c) => check("fixes", engine.fixesForEdges(clone(c.fixes), new Set(c.edge_ids)), c.expected),
};

// --- Running every case ----------------------------------------------------------------------------

const CHECKS = [
  ["inverse_cases.json", "cases", inverseCase],
  ...Object.entries(EDITOR_RUNS).map(([section, run]) => ["editor_cases.json", section, run]),
];

let found = 0;
for (const [name, section, run] of CHECKS) {
  const cases = load(name)[section];
  let reported = 0;
  cases.forEach((c, index) => {
    const label = `${name} ${section} ${JSON.stringify(c.name ?? `#${index}`)}`;
    let line;
    if (typeof c.rule !== "string" || !c.rule) line = `${label}: the case names no rule`;
    else {
      try {
        run(c);
      } catch (error) {
        line =
          error instanceof Difference
            ? `${label} (rule ${c.rule}): ${error.what} differs\n  engine:   ${JSON.stringify(error.actual)}\n  expected: ${JSON.stringify(error.expected)}`
            : `${label} (rule ${c.rule}): the engine threw ${error}`;
      }
    }
    if (line) {
      console.log(line);
      reported += 1;
    }
  });
  console.log(`${name} ${section}: ${cases.length} cases, ${reported} differences`);
  found += reported;
}
console.log(`the editor's engine: ${found} differences`);
process.exitCode = found ? 1 : 0;
