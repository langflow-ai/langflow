/**
 * Pure helpers for the RBAC permission gate. Kept free of React so the gating
 * decision can be unit-tested in isolation.
 *
 * Gating is **fail-open**: when permission data is absent (still loading,
 * request errored, or no provider mounted) every action is allowed. This is a
 * UI affordance gate, not a security boundary — the backend still enforces —
 * so the graceful default for non-RBAC installs is "everything enabled".
 */

import type { EffectivePermissionsResponse } from "@/types/permissions";

/** Normalized lookup map: `{ lowercased_resource_id: [lowercased_actions] }`. */
export type PermissionMap = Record<string, string[]>;

/**
 * Build a case-normalized permission map from an endpoint response.
 *
 * Returns `undefined` when there is no response yet so callers can distinguish
 * "not loaded" (fail-open) from "loaded, empty" (a real, restrictive answer).
 */
export function buildPermissionMap(
  response?: Pick<EffectivePermissionsResponse, "permissions"> | null,
): PermissionMap | undefined {
  if (!response?.permissions) return undefined;
  const map: PermissionMap = {};
  for (const [resourceId, actions] of Object.entries(response.permissions)) {
    map[resourceId.toLowerCase()] = actions.map((action) =>
      action.toLowerCase(),
    );
  }
  return map;
}

/**
 * Decide whether `action` is allowed on `resourceId` given a permission map.
 *
 * Fail-open rules (return `true`):
 *  - `map` is `undefined` (loading / errored / no provider)
 *  - `resourceId` is missing/empty
 *  - the resource id is not present in the map (it was not evaluated)
 *
 * Strict rule: when the resource id **is** present, only the actions listed
 * for it are allowed — an empty list therefore denies every action.
 */
export function canPerformAction(
  map: PermissionMap | undefined,
  resourceId: string | undefined | null,
  action: string,
): boolean {
  if (!map || !resourceId) return true;
  const allowed = map[resourceId.toLowerCase()];
  if (!allowed) return true;
  return allowed.includes(action.toLowerCase());
}
