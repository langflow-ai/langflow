import type { useQueryFunctionType } from "@/types/api";
import type {
  EffectivePermissionsRequest,
  EffectivePermissionsResponse,
  PermissionResourceType,
} from "@/types/permissions";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

/** Backend caps `resource_ids` at 500 per request; mirror it client-side. */
const MAX_RESOURCE_IDS = 500;

export interface UseEffectivePermissionsParams {
  resourceType: PermissionResourceType;
  resourceIds: string[];
  actions?: string[];
  domain?: string;
}

/**
 * Fetch per-resource allowed actions for the current user via
 * `POST /api/v1/authz/me/permissions`.
 *
 * Modeled as a query (not a mutation): it is a cacheable, side-effect-free
 * batch read keyed by the requested resource set, so each list fetches its
 * visible-resource permissions once and the gate reads from cache. The query
 * is disabled when there are no resource ids to evaluate.
 */
export const useGetEffectivePermissions: useQueryFunctionType<
  UseEffectivePermissionsParams,
  EffectivePermissionsResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();
  const { resourceType, resourceIds, actions, domain } = params;

  // Defensive cap: lists are paginated well under 500, but never let a caller
  // send a payload the backend would reject with a 400.
  const cappedIds = resourceIds.slice(0, MAX_RESOURCE_IDS);

  const getEffectivePermissionsFn =
    async (): Promise<EffectivePermissionsResponse> => {
      const body: EffectivePermissionsRequest = {
        resource_type: resourceType,
        resource_ids: cappedIds,
        ...(actions && actions.length > 0 ? { actions } : {}),
        ...(domain ? { domain } : {}),
      };
      const { data } = await api.post<EffectivePermissionsResponse>(
        getURL("AUTHZ_ME_PERMISSIONS"),
        body,
      );
      return data;
    };

  // Sort the variable parts so cache identity is independent of ordering.
  const queryResult = query(
    [
      "useGetEffectivePermissions",
      resourceType,
      [...cappedIds].sort(),
      actions && actions.length > 0 ? [...actions].sort() : "default",
      domain ?? "*",
    ],
    getEffectivePermissionsFn,
    {
      enabled: cappedIds.length > 0,
      staleTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
