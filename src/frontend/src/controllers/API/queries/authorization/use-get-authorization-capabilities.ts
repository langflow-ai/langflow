import useAuthStore from "@/stores/authStore";
import type { useQueryFunctionType } from "@/types/api";
import type { AuthorizationCapabilities } from "@/types/authz";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetAuthorizationCapabilities: useQueryFunctionType<
  undefined,
  AuthorizationCapabilities
> = (options) => {
  const { query } = UseRequestProcessor();
  const userId = useAuthStore((state) => state.userData?.id);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  return query(
    ["authorizationCapabilities", userId ?? "anonymous"],
    async () => {
      const { data } = await api.get<AuthorizationCapabilities>(
        getURL("AUTHZ_CAPABILITIES"),
      );
      return data;
    },
    {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
      ...options,
      enabled: isAuthenticated && (options?.enabled ?? true),
    },
  );
};
