import useAuthStore from "@/stores/authStore";
import type { useQueryFunctionType } from "@/types/api";
import type { AuthorizationTeam, TeamView } from "@/types/authz";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface GetTeamsParams {
  view: TeamView;
  search?: string;
  isActive?: boolean;
  limit?: number;
  offset?: number;
}

export const useGetTeams: useQueryFunctionType<
  GetTeamsParams,
  AuthorizationTeam[]
> = (params, options) => {
  const { query } = UseRequestProcessor();
  const userId = useAuthStore((state) => state.userData?.id);
  return query(
    [
      "authorizationTeams",
      userId ?? "anonymous",
      params.view,
      params.search ?? "",
      params.isActive ?? null,
      params.limit ?? 25,
      params.offset ?? 0,
    ],
    async () => {
      const { data } = await api.get<AuthorizationTeam[]>(
        getURL("AUTHZ_TEAMS"),
        {
          params: {
            view: params.view,
            search: params.search || undefined,
            is_active: params.isActive,
            limit: params.limit ?? 25,
            offset: params.offset ?? 0,
          },
        },
      );
      return data;
    },
    {
      staleTime: 30_000,
      ...options,
      enabled: Boolean(userId) && (options?.enabled ?? true),
    },
  );
};
