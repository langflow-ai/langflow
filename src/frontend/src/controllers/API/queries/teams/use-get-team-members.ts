import useAuthStore from "@/stores/authStore";
import type { useQueryFunctionType } from "@/types/api";
import type { AuthorizationTeamMember } from "@/types/authz";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface GetTeamMembersParams {
  teamId: string;
  limit?: number;
  offset?: number;
}

export const useGetTeamMembers: useQueryFunctionType<
  GetTeamMembersParams,
  AuthorizationTeamMember[]
> = (params, options) => {
  const { query } = UseRequestProcessor();
  const userId = useAuthStore((state) => state.userData?.id);
  return query(
    [
      "authorizationTeamMembers",
      userId ?? "anonymous",
      params.teamId,
      params.limit ?? 50,
      params.offset ?? 0,
    ],
    async () => {
      const { data } = await api.get<AuthorizationTeamMember[]>(
        `${getURL("AUTHZ_TEAMS")}/${params.teamId}/members`,
        {
          params: {
            limit: params.limit ?? 50,
            offset: params.offset ?? 0,
          },
        },
      );
      return data;
    },
    {
      ...options,
      enabled: Boolean(userId && params.teamId) && (options?.enabled ?? true),
    },
  );
};
