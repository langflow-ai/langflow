/**
 * Permission context for the RBAC UI gate.
 *
 * `PermissionsProvider` batches a single `/authz/me/permissions` query for all
 * resource ids visible in a list (or a single resource on a detail surface) and
 * exposes a `can(resourceId, action)` predicate to its subtree. Components call
 * `usePermissions()` to disable/hide affordances the user may not perform.
 *
 * Missing, loading, and failed authorization state is denied by default. The
 * provider enables the compatibility fallback only after the server explicitly
 * reports that authorization enforcement is disabled.
 */

import { keepPreviousData } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext, useMemo } from "react";
import { useGetAuthorizationCapabilities } from "@/controllers/API/queries/authorization";
import { useGetEffectivePermissions } from "@/controllers/API/queries/permissions";
import type {
  PermissionAction,
  PermissionResourceType,
  ResourceCapabilities,
} from "@/types/permissions";
import {
  buildPermissionMap,
  canPerformAction,
  type PermissionMap,
} from "@/utils/permissionUtils";

export interface PermissionsContextValue {
  /** Returns true when `action` is explicitly allowed on `resourceId`. */
  can: (
    resourceId: string | undefined | null,
    action: PermissionAction | string,
  ) => boolean;
  /** Normalized permission map, or `undefined` while unresolved. */
  permissions: PermissionMap | undefined;
  resourceCapabilities: Record<string, ResourceCapabilities> | undefined;
  capability: (
    resourceId: string | undefined | null,
    capability: keyof ResourceCapabilities,
  ) => boolean;
  enforcementActive: boolean | undefined;
  isLoading: boolean;
  isError: boolean;
  isUnavailable: boolean;
}

const DEFAULT_CONTEXT_VALUE: PermissionsContextValue = {
  can: () => false,
  permissions: undefined,
  resourceCapabilities: undefined,
  capability: () => false,
  enforcementActive: undefined,
  isLoading: false,
  isError: true,
  isUnavailable: true,
};

const PermissionsContext = createContext<PermissionsContextValue>(
  DEFAULT_CONTEXT_VALUE,
);

export function usePermissions(): PermissionsContextValue {
  return useContext(PermissionsContext);
}

/** Resolve one capability outside a provider that is already scoped to another resource type. */
export function useResourceCapability(
  resourceType: PermissionResourceType,
  resourceId: string | undefined | null,
  capability: keyof ResourceCapabilities,
): { allowed: boolean; isLoading: boolean; isUnavailable: boolean } {
  const permissions = useGetEffectivePermissions({
    resourceType,
    resourceIds: resourceId ? [resourceId] : [],
  });
  const authorization = useGetAuthorizationCapabilities();
  const explicitlyDisabled =
    authorization.data?.enforcement_active === false && !authorization.isError;
  const isLoading = permissions.isLoading || authorization.isLoading;
  const isUnavailable =
    authorization.isLoading ||
    authorization.isError ||
    authorization.data?.enforcement_active === undefined ||
    (!explicitlyDisabled &&
      (authorization.data?.service_ready !== true ||
        permissions.isLoading ||
        (Boolean(resourceId) && permissions.isError)));
  const resolved = resourceId
    ? permissions.data?.capabilities?.[resourceId]?.[capability]
    : undefined;
  return {
    allowed: !isUnavailable && (resolved ?? explicitlyDisabled),
    isLoading,
    isUnavailable,
  };
}

/**
 * Returns whether a flow detail surface must be treated as read-only.
 *
 * Permission queries fail closed while missing, loading, or errored so a denied
 * user cannot briefly mutate the in-memory canvas.
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
  const {
    data,
    isLoading: permissionsLoading,
    isError: permissionsError,
  } = useGetEffectivePermissions(
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
  const {
    data: authorizationCapabilities,
    isLoading: capabilitiesLoading,
    isError: capabilitiesError,
  } = useGetAuthorizationCapabilities();

  const value = useMemo<PermissionsContextValue>(() => {
    const permissions = buildPermissionMap(data);
    const resourceCapabilities = data?.capabilities
      ? Object.fromEntries(
          Object.entries(data.capabilities).map(
            ([resourceId, capabilities]) => [
              resourceId.toLowerCase(),
              capabilities,
            ],
          ),
        )
      : undefined;
    const enforcementActive = authorizationCapabilities?.enforcement_active;
    const explicitlyDisabled =
      enforcementActive === false && capabilitiesError === false;
    const isLoading = permissionsLoading || capabilitiesLoading;
    const isError = permissionsError || capabilitiesError;
    const isUnavailable =
      capabilitiesLoading ||
      capabilitiesError ||
      enforcementActive === undefined ||
      (!explicitlyDisabled &&
        (authorizationCapabilities?.service_ready !== true ||
          permissionsLoading ||
          permissionsError));
    return {
      permissions,
      resourceCapabilities,
      enforcementActive,
      isLoading,
      isError,
      isUnavailable,
      can: (resourceId, action) =>
        !isUnavailable &&
        canPerformAction(permissions, resourceId, action, explicitlyDisabled),
      capability: (resourceId, capability) => {
        if (isUnavailable) return false;
        if (!resourceId) return explicitlyDisabled;
        const resolved = resourceCapabilities?.[resourceId.toLowerCase()];
        return resolved?.[capability] ?? explicitlyDisabled;
      },
    };
  }, [
    authorizationCapabilities,
    capabilitiesError,
    capabilitiesLoading,
    data,
    permissionsError,
    permissionsLoading,
  ]);

  return (
    <PermissionsContext.Provider value={value}>
      {children}
    </PermissionsContext.Provider>
  );
}
