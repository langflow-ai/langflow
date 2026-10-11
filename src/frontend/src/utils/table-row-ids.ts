import { isEqual } from "lodash";
import ShortUniqueId from "short-unique-id";
import { isRowPosition, orderedRows } from "./flow-operations/canonical";

/**
 * Table rows carry their own identity and order: `_id` names a row and `_pos`
 * is its numeric position. The table's order is the rows' `(_pos, _id)`, not
 * their places in the stored array, which nothing keeps sorted: whatever
 * hands rows out (the grid, an export, the backend before a component runs)
 * puts them in order. A flow's history then records an edit to one cell, an
 * added row or a moved row as a write to that row, so concurrent edits to
 * different rows merge.
 *
 * The editor owns both keys: it assigns them whenever a row appears, and the
 * backend only validates them. Components never see them (the backend strips
 * them before running a component), the grid never shows them, and exported
 * flows leave them out.
 */
export const TABLE_ROW_ID_KEY = "_id";
export const TABLE_ROW_POS_KEY = "_pos";
const TABLE_ROW_KEYS = [TABLE_ROW_ID_KEY, TABLE_ROW_POS_KEY];

const uid = new ShortUniqueId({ length: 10 });

export type TableRow = Record<string, unknown>;

/** A short random row id, unique within one table. */
export function newTableRowId(): string {
  return uid.randomUUID();
}

/** Whether a row key is one of the editor's own (`_id`, `_pos`), not a column. */
export function isTableRowKey(key: string): boolean {
  return TABLE_ROW_KEYS.includes(key);
}

/** Whether a template field holds a table value. */
export function isTableField(field: unknown): boolean {
  if (!field || typeof field !== "object") return false;
  const { type, _input_type } = field as {
    type?: unknown;
    _input_type?: unknown;
  };
  return type === "table" || _input_type === "TableInput";
}

function isRow(row: unknown): row is TableRow {
  return !!row && typeof row === "object" && !Array.isArray(row);
}

function rowId(row: TableRow): string | null {
  const id = row[TABLE_ROW_ID_KEY];
  return typeof id === "string" && id.length > 0 ? id : null;
}

function rowPos(row: TableRow): number | null {
  const pos = row[TABLE_ROW_POS_KEY];
  return isRowPosition(pos) ? pos : null;
}

/** A row without the editor's keys: what a component or an export sees. */
export function stripRowKeys(row: unknown): unknown {
  if (!isRow(row)) return row;
  if (!TABLE_ROW_KEYS.some((key) => key in row)) return row;
  const rest = { ...row };
  for (const key of TABLE_ROW_KEYS) delete rest[key];
  return rest;
}

/** Rows in order and without the editor's keys: what a component or an export sees. */
export function stripTableRowIds(rows: unknown[]): unknown[] {
  return orderedRows(rows).map(stripRowKeys);
}

/** Whether every row has a unique `_id` and a numeric `_pos`: the shape the backend accepts. */
export function hasTableRowIds(rows: unknown): boolean {
  if (!Array.isArray(rows)) return false;
  const seen = new Set<string>();
  for (const row of rows) {
    if (!isRow(row)) return false;
    const id = rowId(row);
    if (id === null || rowPos(row) === null || seen.has(id)) return false;
    seen.add(id);
  }
  return true;
}

/**
 * The same rows, in the same order, each with a unique `_id` and a `_pos`
 * that keeps that order. Rows that already have them keep them; the others
 * get new ones. A row without an id that matches a not yet matched row of
 * `previousRows` (equal apart from the editor's keys) takes that row's id, so
 * a refresh that returns the rows it was given without their ids does not
 * turn every row into a new one.
 *
 * Returns `rows` itself when nothing needed to change.
 */
export function withTableRowIds<T>(rows: T[], previousRows?: unknown): T[] {
  if (hasTableRowIds(rows)) return rows;
  if (!rows.every(isRow)) return rows;

  const previous = Array.isArray(previousRows)
    ? previousRows.filter(isRow).filter((row) => rowId(row) !== null)
    : [];
  const result = (rows as TableRow[]).map((row) => ({ ...row }));

  // Ids: keep the first holder of each id; a row without one, or with an id
  // an earlier row already holds, takes a matching previous row's id or a
  // new one.
  const used = new Set<string>();
  const needId: TableRow[] = [];
  for (const row of result) {
    const id = rowId(row);
    if (id !== null && !used.has(id)) used.add(id);
    else needId.push(row);
  }
  for (const row of needId) {
    const content = stripRowKeys(row);
    const match = previous.find(
      (candidate) =>
        !used.has(rowId(candidate)!) &&
        isEqual(stripRowKeys(candidate), content),
    );
    let id: string;
    if (match) {
      id = rowId(match)!;
      const matchPos = rowPos(match);
      if (rowPos(row) === null && matchPos !== null) {
        row[TABLE_ROW_POS_KEY] = matchPos;
      }
    } else {
      do {
        id = newTableRowId();
      } while (used.has(id));
    }
    used.add(id);
    row[TABLE_ROW_ID_KEY] = id;
  }

  fillMissingPositions(result);
  return result as T[];
}

/**
 * Give each row without a valid position one that keeps it where it is
 * stored, in place: the engine's `fill_missing_positions`. Positioned rows
 * keep their positions. A run of rows without one is spread evenly between
 * the positioned rows stored before and after it, or placed one apart before
 * the first or after the last; when those neighbours are out of order, the
 * run follows the one before it. A table with no positions at all gets `1..n`.
 *
 * When the gap between two neighbours has no room left for the run (doubles
 * run out after about fifty halvings), the whole table is renumbered `1..n`
 * in stored order instead. Only the editor renumbers; the engine never
 * changes a position.
 */
function fillMissingPositions(rows: TableRow[]): void {
  let index = 0;
  while (index < rows.length) {
    if (rowPos(rows[index]) !== null) {
      index++;
      continue;
    }
    let end = index;
    while (end < rows.length && rowPos(rows[end]) === null) end++;
    const count = end - index;
    const before = index > 0 ? rowPos(rows[index - 1]) : null;
    const after = end < rows.length ? rowPos(rows[end]) : null;
    const positions: number[] = [];
    for (let step = 1; step <= count; step++) {
      if (before !== null && after !== null && before < after)
        positions.push(before + ((after - before) * step) / (count + 1));
      else if (before !== null) positions.push(before + step);
      else if (after !== null) positions.push(after - count - 1 + step);
      else positions.push(step);
    }
    if (!fitsBetween(positions, before, after)) {
      rows.forEach((row, slot) => {
        row[TABLE_ROW_POS_KEY] = slot + 1;
      });
      return;
    }
    positions.forEach((position, step) => {
      rows[index + step][TABLE_ROW_POS_KEY] = position;
    });
    index = end;
  }
}

/** Whether new positions are distinct and strictly between their neighbours, when those are in order. */
function fitsBetween(
  positions: number[],
  before: number | null,
  after: number | null,
): boolean {
  if (before === null || after === null || before >= after) return true;
  let previous = before;
  for (const position of positions) {
    if (position <= previous) return false;
    previous = position;
  }
  return previous < after;
}

/**
 * Rows appended after `rows`, each with a new `_id` and a `_pos` one past the
 * last position. Keys the new rows carried (a duplicated row's) are replaced.
 */
export function appendTableRows<T>(rows: T[], newRows: unknown[]): T[] {
  const base = withTableRowIds(rows);
  const used = new Set(base.map((row) => rowId(row as TableRow)));
  let last = 0;
  for (const row of base) last = Math.max(last, rowPos(row as TableRow)!);
  const appended = newRows.map((row) => {
    const fresh = { ...(stripRowKeys(row) as TableRow) };
    let id: string;
    do {
      id = newTableRowId();
    } while (used.has(id));
    used.add(id);
    last = Math.floor(last) + 1;
    fresh[TABLE_ROW_ID_KEY] = id;
    fresh[TABLE_ROW_POS_KEY] = last;
    return fresh as T;
  });
  return [...base, ...appended];
}

type TemplateLike = Record<string, unknown>;

/**
 * A template whose table values have row ids. A table whose value equals the
 * one in `previousTemplate` is left as it is, ids or not: only a table that
 * appears or changes is written with ids, so opening or refreshing a flow
 * never rewrites an untouched legacy table, and the first edit to one writes
 * it whole, with ids.
 *
 * Returns `template` itself when nothing needed to change.
 */
export function withTemplateTableRowIds<T extends TemplateLike | undefined>(
  template: T,
  previousTemplate?: TemplateLike,
): T {
  if (!template || typeof template !== "object") return template;
  let result: TemplateLike | null = null;
  for (const [name, field] of Object.entries(template)) {
    if (!isTableField(field)) continue;
    const value = (field as { value?: unknown }).value;
    if (!Array.isArray(value)) continue;
    const previousField = previousTemplate?.[name] as
      | { value?: unknown }
      | undefined;
    if (previousField && isEqual(previousField.value, value)) continue;
    const withIds = withTableRowIds(value, previousField?.value);
    if (withIds === value) continue;
    result ??= { ...template };
    result[name] = { ...(field as object), value: withIds };
  }
  return (result ?? template) as T;
}

type NodeLike = {
  id: string;
  data?: { node?: { template?: TemplateLike } & Record<string, unknown> };
} & Record<string, unknown>;

/**
 * A node whose table values have row ids, compared against the same node as
 * it was (`previousNode`); a node that is new gets ids on every table.
 *
 * Returns `node` itself when nothing needed to change.
 */
export function withNodeTableRowIds<T extends NodeLike>(
  node: T,
  previousNode?: NodeLike,
): T {
  const template = node?.data?.node?.template;
  if (!template) return node;
  const next = withTemplateTableRowIds(
    template,
    previousNode?.data?.node?.template,
  );
  if (next === template) return node;
  return {
    ...node,
    data: {
      ...node.data,
      node: { ...node.data!.node, template: next },
    },
  };
}

/**
 * Nodes whose table values have row ids, each compared against the node with
 * the same id in `previousNodes`.
 *
 * Returns `nodes` itself when nothing needed to change.
 */
export function withNodesTableRowIds<T extends NodeLike>(
  nodes: T[],
  previousNodes: NodeLike[] = [],
): T[] {
  const previousById = new Map(previousNodes.map((node) => [node.id, node]));
  let changed = false;
  const result = nodes.map((node) => {
    const next = withNodeTableRowIds(node, previousById.get(node.id));
    if (next !== node) changed = true;
    return next;
  });
  return changed ? result : nodes;
}

type GraphLike = { nodes?: unknown[] } | null | undefined;

/**
 * Strips the editor's row keys from every table in a graph, including the
 * graphs of group nodes, in place. Exported flows stay as older Langflow
 * versions expect them.
 */
export function stripTableRowIdsFromGraph(graph: GraphLike): void {
  if (!graph || !Array.isArray(graph.nodes)) return;
  for (const node of graph.nodes as NodeLike[]) {
    const nodeData = node?.data?.node;
    const template = nodeData?.template;
    if (template && typeof template === "object") {
      for (const field of Object.values(template)) {
        if (!isTableField(field)) continue;
        const holder = field as { value?: unknown };
        if (Array.isArray(holder.value)) {
          holder.value = stripTableRowIds(holder.value);
        }
      }
    }
    const subFlow = nodeData?.flow as { data?: GraphLike } | undefined;
    stripTableRowIdsFromGraph(subFlow?.data);
  }
}
