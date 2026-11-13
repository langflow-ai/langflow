/**
 * The edge fixes a history preview made, as operations a restore can send.
 *
 * A revision can hold edges the edge rules refuse, which only the client can
 * fix. The preview already shows them fixed: `cleanEdges` drops the edges
 * whose handles no longer exist and rewrites handles stored in another
 * spelling. A restore refused for such edges is resent with these fixes, and
 * the server applies them to the revision it rebuilds (see ops-history,
 * "Repair").
 */

import type { FlowOperation } from "./apply";
import { valuesEqual } from "./canonical";
import { HANDLE_KEYS } from "./edge-rules";

type JsonObject = Record<string, unknown>;

function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/**
 * The operations that turn a revision's edges as read (`read`) into the edges
 * its preview shows (`shown`): a `delete_edges` for the edges the preview
 * dropped or whose handles it rewrote, and an `add_edges` that adds the
 * rewritten ones back. An edge never changes in place, so a rewritten edge is
 * deleted and added again with the same id. Empty when the preview changed no
 * edge.
 */
export function edgeFixes(
  read: JsonObject[],
  shown: JsonObject[],
): FlowOperation[] {
  const shownById = new Map(shown.map((edge) => [edge.id as string, edge]));
  const deleted: string[] = [];
  const added: JsonObject[] = [];
  for (const edge of read) {
    const id = edge.id as string;
    const fixed = shownById.get(id);
    if (!fixed) {
      deleted.push(id);
      continue;
    }
    const rewritten = withHandlesOf(edge, fixed);
    if (!valuesEqual(edge, rewritten)) {
      deleted.push(id);
      added.push(rewritten);
    }
  }
  const fixes: FlowOperation[] = [];
  if (deleted.length > 0) fixes.push({ type: "delete_edges", ids: deleted });
  if (added.length > 0) fixes.push({ type: "add_edges", edges: added });
  return fixes;
}

/**
 * A copy of `edge` with the handles of `shown`, in both forms. A handle that
 * `shown` lacks is removed. An edge without a `data` object gets one that
 * holds only the handles.
 */
function withHandlesOf(edge: JsonObject, shown: JsonObject): JsonObject {
  const shownData = isObject(shown.data) ? shown.data : {};
  const data: JsonObject = isObject(edge.data) ? { ...edge.data } : {};
  const rewritten: JsonObject = { ...edge, data };
  for (const key of HANDLE_KEYS) {
    if (shown[key] !== undefined) rewritten[key] = shown[key];
    else delete rewritten[key];
    if (shownData[key] !== undefined) data[key] = shownData[key];
    else delete data[key];
  }
  return rewritten;
}

/**
 * The part of `fixes` that touches the given edges: a restore sends fixes only
 * for the edges the server flagged, since the preview also respells handles
 * that break no rule, which the server would refuse as fixes.
 */
export function fixesForEdges(
  fixes: FlowOperation[],
  edgeIds: Set<string>,
): FlowOperation[] {
  const kept: FlowOperation[] = [];
  for (const fix of fixes) {
    if (fix.type === "delete_edges") {
      const ids = (fix.ids as string[]).filter((id) => edgeIds.has(id));
      if (ids.length > 0) kept.push({ ...fix, ids });
    } else if (fix.type === "add_edges") {
      const edges = (fix.edges as JsonObject[]).filter((edge) =>
        edgeIds.has(edge.id as string),
      );
      if (edges.length > 0) kept.push({ ...fix, edges });
    }
  }
  return kept;
}
