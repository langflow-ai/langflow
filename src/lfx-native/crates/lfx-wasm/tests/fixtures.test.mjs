// Every shared fixture file, run through the browser binding's Node build.
//
// The fixtures are the engine's specification; the Rust runner and the Python
// binding's runner run the same files with the same checks. Numbers keep
// their original text through the binding, so fixtures are read with each
// number as raw JSON (JSON.rawJSON), and compared as text where the Rust
// runner compares text.

import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { describe, test } from "node:test";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const ops = createRequire(import.meta.url)(join(here, "../pkg/node/lfx_native.js"));
const FIXTURES = join(here, "../../../fixtures");
const GENERATED_EDGE_ID = "<generated edge id>";
const GENERATED_ROW_ID = "<generated row id>";

/** Parse JSON keeping every number as its original text. */
function parse(text) {
  return JSON.parse(text, (_key, value, context) =>
    typeof value === "number" ? JSON.rawJSON(context.source) : value,
  );
}

const dump = (value) => JSON.stringify(value);
const load = (name) => parse(readFileSync(join(FIXTURES, name), "utf8"));
const isNumber = (value) => JSON.isRawJSON(value);
const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value) && !isNumber(value);

/** Equal as JSON: objects in any key order, numbers by their text. */
function strict(actual, expected) {
  if (isNumber(actual) || isNumber(expected)) return isNumber(actual) && isNumber(expected) && actual.rawJSON === expected.rawJSON;
  if (Array.isArray(actual) || Array.isArray(expected))
    return Array.isArray(actual) && Array.isArray(expected) && actual.length === expected.length && actual.every((item, i) => strict(item, expected[i]));
  if (isObject(actual) || isObject(expected)) {
    if (!isObject(actual) || !isObject(expected)) return false;
    const keys = Object.keys(actual);
    return keys.length === Object.keys(expected).length && keys.every((key) => key in expected && strict(actual[key], expected[key]));
  }
  return actual === expected;
}

/** Equal as JSON, numbers by value, and a generated-id placeholder matching any id of its shape. */
function matches(actual, expected) {
  if (expected === GENERATED_EDGE_ID) return typeof actual === "string" && /^e-[0-9A-Za-z]{21}$/.test(actual);
  if (expected === GENERATED_ROW_ID) return typeof actual === "string" && /^[0-9A-Za-z]{10}$/.test(actual);
  if (isNumber(actual) || isNumber(expected)) return isNumber(actual) && isNumber(expected) && Number(actual.rawJSON) === Number(expected.rawJSON);
  if (Array.isArray(actual) || Array.isArray(expected))
    return Array.isArray(actual) && Array.isArray(expected) && actual.length === expected.length && actual.every((item, i) => matches(item, expected[i]));
  if (isObject(actual) || isObject(expected)) {
    if (!isObject(actual) || !isObject(expected)) return false;
    const keys = Object.keys(actual);
    return keys.length === Object.keys(expected).length && keys.every((key) => key in expected && matches(actual[key], expected[key]));
  }
  return actual === expected;
}

function check(compare, what, actual, expected) {
  assert.ok(compare(actual, expected), `${what} differs\n  actual:   ${dump(actual)}\n  expected: ${dump(expected)}`);
}

/** The outcome of a call: its value, or the engine error it threw. */
function outcome(run) {
  try {
    return { value: run() };
  } catch (error) {
    if (typeof error?.kind !== "string") throw error;
    return { error };
  }
}

const failure = (error) => ({ error: error.kind, code: error.code });
const graphText = (c, key) => (`${key}_json` in c ? c[`${key}_json`] : dump(c[key] ?? null));
const num = (value) => Number(value.rawJSON);

function cases(name, section, run) {
  describe(`${name}::${section}`, () => {
    for (const c of load(name)[section]) test(c.name ?? "case", () => run(c));
  });
}

// --- apply_cases.json, merge_cases.json, property_cases.json -------------------------------

const ignoringIdOrder = (operations) =>
  operations.map((op) => (op.type === "delete_nodes" || op.type === "delete_edges" ? { ...op, ids: [...op.ids].sort() } : op));

function ignoringRowOrder(flow) {
  const copy = parse(dump(flow));
  for (const node of copy.nodes ?? []) {
    for (const name of JSON.parse(ops.tableFields(dump(node)))) {
      const field = node.data.node.template[name];
      field.value = [...field.value].sort((a, b) => (a._id < b._id ? -1 : a._id > b._id ? 1 : 0));
    }
  }
  return copy;
}

cases("apply_cases.json", "cases", (c) => {
  const created = outcome(() => new ops.FlowState(dump(c.base)));
  if (created.error) return check(strict, "error", failure(created.error), { error: c.error, code: c.code });
  const state = created.value;
  const applied = outcome(() => parse(state.apply(dump(c.operations), { forward: true })));
  if (applied.error) {
    check(strict, "error", failure(applied.error), { error: c.error, code: c.code });
    return check(strict, "state after the refused batch", parse(state.toJson()), c.base);
  }
  assert.ok(!c.error, "expected the operations to be refused");
  check(strict, "flow data", ignoringRowOrder(parse(state.toJson())), ignoringRowOrder(c.expected));
  check(strict, "forward operations", ignoringIdOrder(applied.value.forward_operations), ignoringIdOrder(c.forward_operations ?? c.operations));
});

const merge = load("merge_cases.json");
cases("merge_cases.json", "cases", (c) => {
  const state = new ops.FlowState(dump(merge.base));
  const outcomes = {};
  for (const name of c.order) {
    const before = parse(state.toJson());
    const result = outcome(() => state.apply(dump(c.transactions[name]), {}));
    if (result.error) {
      check(strict, `state after refusing ${name}`, parse(state.toJson()), before);
      outcomes[name] = failure(result.error);
    } else outcomes[name] = "applied";
  }
  check(strict, "outcomes", outcomes, c.outcomes);
  assert.ok(ops.graphsEqual(state.toJson(), dump(c.expected)));
});

const property = load("property_cases.json");
cases("property_cases.json", "sequences", (sequence) => {
  const state = new ops.FlowState(dump(property.base));
  for (const transaction of sequence.transactions) state.apply(dump(transaction), {});
  assert.equal(ops.graphHash(state.toJson()), sequence.graph_hash);
});

// --- diff_cases.json, canonical_cases.json ----------------------------------------------------

cases("diff_cases.json", "cases", (c) => {
  const [base, target] = [dump(c.base), dump(c.target)];
  check(strict, "operations", parse(ops.diff(base, target)), c.operations);
  assert.ok(ops.graphsEqual(dump(parse(ops.derive(base, target)).flow_data), target));
  const state = new ops.FlowState(base);
  for (const operation of c.operations) state.apply(dump([operation]), {});
  assert.ok(ops.graphsEqual(state.toJson(), target));
});

for (const section of ["numbers", "values"]) {
  cases("canonical_cases.json", section, (c) => {
    const result = outcome(() => ops.canonicalJson(c.json));
    const actual = result.error ? { error: failure(result.error) } : { canonical: result.value };
    check(strict, "canonical form", actual, c.error ? { error: c.error } : { canonical: c.canonical });
  });
}

test("canonical_cases.json::equality_samples", () => {
  const samples = load("canonical_cases.json").equality_samples;
  for (const left of samples)
    for (const right of samples) assert.equal(ops.valuesEqual(left.json, right.json), left.canonical === right.canonical);
});

cases("canonical_cases.json", "graphs", (c) => {
  const [left, right] = [dump(c.left), dump(c.right)];
  assert.equal(ops.graphsEqual(left, right), c.equal);
  assert.equal(ops.graphHash(left), c.left_hash);
  assert.equal(ops.graphHash(right), c.right_hash);
});

// --- validation_cases.json, repair_cases.json --------------------------------------------------

cases("validation_cases.json", "cases", (c) => {
  const base = "base" in c ? dump(c.base) : undefined;
  const result = outcome(() => parse(ops.validate(graphText(c, "flow"), base, c.check_values ?? true)));
  const actual = result.error ? { error: failure(result.error) } : { violations: result.value };
  check(strict, "violations", actual, c.error ? { error: c.error } : { violations: c.violations });
});

cases("repair_cases.json", "cases", (c) => {
  const base = "base" in c ? dump(c.base) : undefined;
  const result = outcome(() => parse(ops.repair(graphText(c, "flow"), base)));
  const actual = result.error
    ? { error: { ...failure(result.error), violations: parse(result.error.details).violations ?? [] } }
    : { expected: result.value.flow_data, fixes: result.value.fixes };
  check(matches, "repair", actual, c.error ? { error: c.error } : { expected: c.expected, fixes: c.fixes });
});

// --- table_cases.json, editor_cases.json ---------------------------------------------------------

const tableRuns = {
  strip: (c) => ops.stripRowKeys(dump(c.rows)),
  ordered: (c) => ops.orderedRows(dump(c.rows)),
  assign: (c) => ops.assignRowIds(dump(c.rows), c.previous == null ? undefined : dump(c.previous), false),
  assign_node: (c) => ops.assignTableRowIds(dump(c.node), false),
  assign_changed: (c) => ops.assignChangedTableRowIds(dump(c.base), dump(c.target), false),
  strip_flow: (c) => ops.stripFlowTableRowKeys(dump(c.flow)),
};
for (const [section, run] of Object.entries(tableRuns)) {
  cases("table_cases.json", section, (c) => check(matches, section, parse(run(c)), c.expected));
}

cases("table_cases.json", "fill_positions", (c) => {
  // The binding fills positions as part of assigning row ids. Rows that
  // already have unique ids show only the positions it filled.
  const rows = c.rows.map((row, index) => ({ ...row, _id: `row${index}` }));
  const assigned = parse(ops.assignRowIds(dump(rows), undefined, false));
  check(matches, "positions", assigned.map((row) => row._pos ?? null), c.expected.map((row) => row._pos ?? null));
});

cases("editor_cases.json", "assign", (c) =>
  check(matches, "rows", parse(ops.assignRowIds(dump(c.rows), c.previous ? dump(c.previous) : undefined, true)), c.expected),
);
cases("editor_cases.json", "append", (c) => check(matches, "rows", parse(ops.appendTableRows(dump(c.rows), dump(c.new_rows))), c.expected));
cases("editor_cases.json", "assign_nodes", (c) => {
  const target = parse(ops.assignChangedTableRowIds(dump({ nodes: c.previous }), dump({ nodes: c.nodes }), true));
  check(matches, "nodes", target.nodes, c.expected);
});
cases("editor_cases.json", "edge_fixes", (c) => check(matches, "fixes", parse(ops.edgeFixes(dump(c.read), dump(c.shown))), c.fixes));
cases("editor_cases.json", "fixes_for_edges", (c) =>
  check(matches, "fixes", parse(ops.fixesForEdges(dump(c.fixes), dump(c.edge_ids))), c.expected),
);

// --- inverse_cases.json ------------------------------------------------------------------------

function unordered(lists) {
  const keys = { delete_nodes: "ids", delete_edges: "ids", add_nodes: "nodes", add_edges: "edges" };
  const id = (item) => (typeof item === "string" ? item : item.id);
  return lists.map((operations) =>
    operations.map((op) => (keys[op.type] ? { ...op, [keys[op.type]]: [...op[keys[op.type]]].sort((a, b) => (id(a) < id(b) ? -1 : 1)) } : op)),
  );
}

cases("inverse_cases.json", "cases", (c) => {
  const state = new ops.FlowState(dump(c.base));
  const applied = parse(state.apply(dump(c.operations), { inverse: true }));
  check(matches, "inverse operations", unordered(applied.inverse_operations), unordered(c.inverse));
  for (const inverse of [...applied.inverse_operations].reverse()) state.apply(dump(inverse), { restoring: true });
  assert.ok(ops.graphsEqual(state.toJson(), dump(c.base)));
});

// --- envelope_cases.json, replay_cases.json -------------------------------------------------------

const corruption = (error) => {
  const details = parse(error.details);
  return { error: { kind: details.damage, revision: details.revision } };
};

cases("envelope_cases.json", "decode", (c) => {
  const result = outcome(() => parse(ops.decodeRow(dump(c.row))));
  const actual = result.error ? corruption(result.error) : { decoded: result.value };
  check(strict, "decoded row", actual, c.error ? { error: c.error } : { decoded: c.decoded });
});

cases("envelope_cases.json", "encode", (c) => {
  const { envelope, actor_user_ids, request_ids } = c;
  check(strict, "envelope", parse(ops.encodeEnvelope(dump(c.operations))), { envelope, actor_user_ids, request_ids });
});

cases("envelope_cases.json", "pack", (c) => {
  const options = { latest_revision: c.latest_revision, actor_user_id: c.actor_user_id, request_id: c.request_id, limits: c.limits };
  if ("cause" in c) options.cause = c.cause;
  check(strict, "rows", parse(ops.pack(dump(c.operations), dump(options))), c.rows);
});

cases("replay_cases.json", "cases", (c) => {
  const result = outcome(() => parse(ops.replay(dump(c.checkpoint), num(c.checkpoint_revision), dump(c.rows), num(c.revision))));
  const actual = result.error ? corruption(result.error) : { expected: result.value };
  check(strict, "replayed graph", actual, c.error ? { error: c.error } : { expected: c.expected });
});

cases("replay_cases.json", "verify", (c) => {
  const result = outcome(() => ops.verifyCheckpoint(dump(c.graph), c.hash, num(c.revision)));
  check(strict, "verification", result.error ? corruption(result.error) : {}, c.error ? { error: c.error } : {});
});

// --- restore_cases.json, write_cases.json ----------------------------------------------------------

cases("restore_cases.json", "cases", (c) => {
  const result = outcome(() => parse(ops.applyRestoreFixes(dump(c.revision), dump(c.stored), dump(c.fixes))));
  const actual = result.error ? { error: failure(result.error) } : { expected: result.value };
  check(strict, "restored revision", actual, c.error ? { error: c.error } : { expected: c.expected });
});

cases("write_cases.json", "cases", (c) => {
  const result = outcome(() => parse(ops.prepareWrite(dump(c.stored), dump(c.target), dump(c.options))));
  let actual;
  if (result.error) {
    const details = parse(result.error.details);
    actual = { error: { graph: details.graph, violations: details.violations } };
  } else actual = { expected: result.value };
  check(matches, "prepared write", actual, c.error ? { error: c.error } : { expected: c.expected });
});

test("every fixture file is run", () => {
  const run = [
    "apply_cases.json", "canonical_cases.json", "diff_cases.json", "editor_cases.json", "envelope_cases.json",
    "inverse_cases.json", "merge_cases.json", "property_cases.json", "repair_cases.json", "replay_cases.json",
    "restore_cases.json", "table_cases.json", "validation_cases.json", "write_cases.json",
  ];
  assert.deepEqual(readdirSync(FIXTURES).filter((name) => name.endsWith(".json")).sort(), run);
});
