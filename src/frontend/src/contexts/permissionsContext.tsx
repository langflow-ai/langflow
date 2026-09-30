/**
 * Permission context for the RBAC UI gate.
 *
 * `PermissionsProvider` batches a single `/authz/me/permissions` query for all
 * resource ids visible in a list (or a single resource on a detail surface) and
 * exposes a `can(resourceId, action)` predicate to its subtree. Components call
 * `usePermissions()` to disable/hide affordances the user may not perform.
 *
 * When no provider is mounted, `usePermissions()` returns a fail-open default
 * (`can` always `true`) so components that opt into gating stay enabled in
 * contexts where permissions were never resolved — matching the non-RBAC
 * graceful default.
 */

import { keepPreviousData } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext, useMemo } from "react";
import { useGetEffectivePermissions } from "@/controllers/API/queries/permissions";
import type {
  PermissionAction,
  PermissionResourceType,
} from "@/types/permissions";
import {
  buildPermissionMap,
  canPerformAction,
  type PermissionMap,
} from "@/utils/permissionUtils";

export interface PermissionsContextValue {
  /** Returns true when `action` is allowed on `resourceId` (fail-open). */
  can: (
    resourceId: string | undefined | null,
    action: PermissionAction | string,
  ) => boolean;
  /** Normalized permission map, or `undefined` while unresolved. */
  permissions: PermissionMap | undefined;
  isLoading: boolean;
  isError: boolean;
}

const DEFAULT_CONTEXT_VALUE: PermissionsContextValue = {
  can: () => true,
  permissions: undefined,
  isLoading: false,
  isError: false,
};

const PermissionsContext = createContext<PermissionsContextValue>(
  DEFAULT_CONTEXT_VALUE,
);

export function usePermissions(): PermissionsContextValue {
  return useContext(PermissionsContext);
}

/**
 * Returns whether a flow detail surface must be treated as read-only.
 *
 * Permission queries intentionally fail open on errors and when no provider is
 * mounted. While an active provider is still resolving, however, flow editors
 * fail closed so a denied user cannot briefly mutate the in-memory canvas.
 */
export function useIsFlowReadOnly(flowId: string | undefined | null): boolean {
  const { can, isLoading } = usePermissions();
  return Boolean(flowId) && (isLoading || !can(flowId, "write"));
}

/**
 * Returns whether the read-only verdict for `flowId` is still unresolved.
 *
 * This is the transient half of `useIsFlowReadOnly`: both are true while the
 * provider resolves, but only this one clears once the answer arrives. Controls
 * that invoke a gated mutation read it to disable themselves for the same
 * window the gate rejects them, so the click is refused visibly instead of
 * being discarded, and to tell "checking" apart from "not allowed" in the
 * reason they surface.
 */
export function useIsFlowPermissionPending(
  flowId: string | undefined | null,
): boolean {
  const { isLoading } = usePermissions();
  return Boolean(flowId) && isLoading;
}

export interface PermissionsProviderProps {
  resourceType: PermissionResourceType;
  resourceIds: string[];
  /** Actions to resolve. Defaults to the backend's full vocabulary. */
  actions?: string[];
  /** Authorization domain — e.g. `project:{folderId}`. Defaults to `*`. */
  domain?: string;
  /** Keep the prior permission map while a changed resource set resolves. */
  preservePreviousPermissions?: boolean;
  children: ReactNode;
}

export function PermissionsProvider({
  resourceType,
  resourceIds,
  actions,
  domain,
  preservePreviousPermissions = false,
  children,
}: PermissionsProviderProps) {
  const { data, isLoading, isError } = useGetEffectivePermissions(
    {
      resourceType,
      resourceIds,
      actions,
      domain,
    },
    preservePreviousPermissions
      ? { placeholderData: keepPreviousData }
      : undefined,
  );

  const value = useMemo<PermissionsContextValue>(() => {
    const permissions = buildPermissionMap(data);
    return {
      permissions,
      isLoading,
      isError,
      can: (resourceId, action) =>
        canPerformAction(permissions, resourceId, action),
    };
  }, [data, isLoading, isError]);

  return (
    <PermissionsContext.Provider value={value}>
      {children}
    </PermissionsContext.Provider>
  );
}
