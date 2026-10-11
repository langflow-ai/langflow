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

import type { FieldUpdate, FlowOperation } from "./apply";
import { valuesEqual } from "./canonical";
import { HANDLE_KEYS } from "./edge-rules";

type JsonObject = Record<string, unknown>;

function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/**
 * The operations that turn a revision's edges as read (`read`) into the edges
 * its preview shows (`shown`): a `delete_edges` for the edges the preview
 * dropped, and an `update_edges` for the handles it rewrote. Empty when the
 * preview changed no edge.
 */
export function edgeFixes(
  read: JsonObject[],
  shown: JsonObject[],
): FlowOperation[] {
  const shownById = new Map(shown.map((edge) => [edge.id as string, edge]));
  const dropped: string[] = [];
  const updates: FieldUpdate[] = [];
  for (const edge of read) {
    const id = edge.id as string;
    const fixed = shownById.get(id);
    if (!fixed) {
      dropped.push(id);
      continue;
    }
    for (const key of HANDLE_KEYS) {
      if (!valuesEqual(edge[key] ?? null, fixed[key] ?? null))
        updates.push({ id, op: "set_field", path: [key], value: fixed[key] });
    }
    const data = edge.data;
    const fixedData = isObject(fixed.data) ? fixed.data : {};
    const handles: JsonObject = {};
    for (const key of HANDLE_KEYS) handles[key] = fixedData[key];
    if (!isObject(data)) {
      updates.push({ id, op: "set_field", path: ["data"], value: handles });
      continue;
    }
    for (const key of HANDLE_KEYS) {
      if (!valuesEqual(data[key] ?? null, handles[key] ?? null))
        updates.push({
          id,
          op: "set_field",
          path: ["data", key],
          value: handles[key],
        });
    }
  }
  const fixes: FlowOperation[] = [];
  if (dropped.length > 0) fixes.push({ type: "delete_edges", ids: dropped });
  if (updates.length > 0) fixes.push({ type: "update_edges", updates });
  return fixes;
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
    } else {
      const updates = (fix.updates as FieldUpdate[]).filter((update) =>
        edgeIds.has(update.id),
      );
      if (updates.length > 0) kept.push({ ...fix, updates });
    }
  }
  return kept;
}
