import useAuthStore from "@/stores/authStore";
import type { useQueryFunctionType } from "@/types/api";
import type {
  AuthorizationRecipientPage,
  ShareRecipientType,
  ShareResourceType,
} from "@/types/authz";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface RecipientSearchParams {
  purpose: "share" | "team_membership";
  kind: ShareRecipientType;
  query: string;
  resourceType?: ShareResourceType;
  resourceId?: string;
  teamId?: string;
  limit?: number;
  offset?: number;
}

export const useSearchAuthorizationRecipients: useQueryFunctionType<
  RecipientSearchParams,
  AuthorizationRecipientPage
> = (params, options) => {
  const { query } = UseRequestProcessor();
  const userId = useAuthStore((state) => state.userData?.id);
  const normalizedQuery = params.query.trim();

  return query(
    [
      "authorizationRecipients",
      userId ?? "anonymous",
      params.purpose,
      params.kind,
      params.resourceType ?? null,
      params.resourceId ?? null,
      params.teamId ?? null,
      normalizedQuery,
      params.limit ?? 20,
      params.offset ?? 0,
    ],
    async () => {
      const { data } = await api.get<AuthorizationRecipientPage>(
        getURL("AUTHZ_RECIPIENTS"),
        {
          params: {
            purpose: params.purpose,
            kind: params.kind,
            q: normalizedQuery,
            resource_type: params.resourceType,
            resource_id: params.resourceId,
            team_id: params.teamId,
            limit: params.limit ?? 20,
            offset: params.offset ?? 0,
          },
        },
      );
      return data;
    },
    {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      ...options,
      enabled:
        Boolean(userId) &&
        normalizedQuery.length >= 2 &&
        (options?.enabled ?? true),
    },
  );
};
