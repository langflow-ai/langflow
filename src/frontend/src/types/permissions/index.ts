/**
 * Types for the RBAC permission-gating layer.
 *
 * Mirrors the backend contract of `POST /api/v1/authz/me/permissions`
 * (see `langflow/api/v1/authz_me.py`). The OSS pass-through returns every
 * requested action for every resource id, so gating on the returned action
 * list keeps all controls enabled when authorization is disabled.
 */

/** Resource slugs accepted by the `/authz/me/permissions` endpoint. */
export const PERMISSION_RESOURCE_TYPES = [
  "flow",
  "deployment",
  "project",
  "knowledge_base",
  "variable",
  "file",
  "component",
] as const;

export type PermissionResourceType = (typeof PERMISSION_RESOURCE_TYPES)[number];

/** Default action vocabulary, aligned with the backend `_DEFAULT_ACTIONS`. */
export const DEFAULT_PERMISSION_ACTIONS = [
  "read",
  "write",
  "execute",
  "delete",
  "create",
] as const;

export type PermissionAction = (typeof DEFAULT_PERMISSION_ACTIONS)[number];

/** Request body for `POST /api/v1/authz/me/permissions`. */
export interface EffectivePermissionsRequest {
  resource_type: PermissionResourceType;
  /** Resource ids to evaluate. Backend caps this at 500 per request. */
  resource_ids: string[];
  /** Actions to check. Omit to use the backend default vocabulary. */
  actions?: string[];
  /** Authorization domain — typically `project:{id}` or `*`. */
  domain?: string;
}

/**
 * Response: `{ resource_id: [allowed_actions] }`. An empty list for a
 * resource id means the user may perform none of the requested actions on it.
 */
export interface EffectivePermissionsResponse {
  resource_type: PermissionResourceType;
  permissions: Record<string, string[]>;
}
