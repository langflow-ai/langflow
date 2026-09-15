import useAuthStore from "@/stores/authStore";
import type { useQueryFunctionType } from "@/types/api";
import type { AuthorizationTeam } from "@/types/authz";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetTeam: useQueryFunctionType<string, AuthorizationTeam> = (
  teamId,
  options,
) => {
  const { query } = UseRequestProcessor();
  const userId = useAuthStore((state) => state.userData?.id);
  return query(
    ["authorizationTeam", userId ?? "anonymous", teamId],
    async () => {
      const { data } = await api.get<AuthorizationTeam>(
        `${getURL("AUTHZ_TEAMS")}/${teamId}`,
      );
      return data;
    },
    {
      ...options,
      enabled: Boolean(userId && teamId) && (options?.enabled ?? true),
    },
  );
};
