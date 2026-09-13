/**
 * Pure helpers for the RBAC permission gate. Kept free of React so the gating
 * decision can be unit-tested in isolation.
 *
 * Gating is fail-closed unless the server explicitly reports disabled enforcement.
 * Missing, loading, errored, or unevaluated permission data denies protected
 * actions. The only unresolved allow path requires an explicit server response
 * confirming that authorization enforcement is disabled.
 */

import type { EffectivePermissionsResponse } from "@/types/permissions";

/** Normalized lookup map: `{ lowercased_resource_id: [lowercased_actions] }`. */
export type PermissionMap = Record<string, string[]>;

/**
 * Build a case-normalized permission map from an endpoint response.
 *
 * Returns `undefined` when there is no response yet so callers can distinguish
 * "not loaded" from "loaded, empty" (a real, restrictive answer).
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
 * Missing state denies unless `allowWhenUnresolved` is true because the server
 * explicitly confirmed disabled enforcement. A present entry allows only its
 * listed actions; an empty list denies every action.
 */
export function canPerformAction(
  map: PermissionMap | undefined,
  resourceId: string | undefined | null,
  action: string,
  allowWhenUnresolved = false,
): boolean {
  if (!map || !resourceId) return allowWhenUnresolved;
  const allowed = map[resourceId.toLowerCase()];
  if (!allowed) return allowWhenUnresolved;
  return allowed.includes(action.toLowerCase());
}
