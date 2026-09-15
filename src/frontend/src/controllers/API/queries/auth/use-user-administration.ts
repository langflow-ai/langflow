import type { QueryClient } from "@tanstack/react-query";
import useAuthStore from "@/stores/authStore";
import type {
  Users,
  useMutationFunctionType,
  useQueryFunctionType,
} from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { invalidateAuthorizationState } from "../authorization/cache";

export interface AdminUsersParams {
  skip: number;
  limit: number;
  search?: string;
}

interface AdminUsersResponse {
  users: Users[];
  total_count: number;
}

export interface AdminUserFields {
  username?: string;
  password?: string;
  is_active?: boolean;
  is_superuser?: boolean;
}

export const useGetAdminUsers: useQueryFunctionType<
  AdminUsersParams,
  AdminUsersResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();
  const userId = useAuthStore((state) => state.userData?.id);
  return query(
    ["adminUsers", userId, params.skip, params.limit, params.search ?? ""],
    async ({ signal }) => {
      const { data } = await api.get<AdminUsersResponse>(
        `${getURL("USERS")}/`,
        { params, signal },
      );
      return data;
    },
    { ...options, enabled: Boolean(userId) && (options?.enabled ?? true) },
  );
};

async function refreshUserAdministration(queryClient: QueryClient) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["adminUsers"] }),
    invalidateAuthorizationState(queryClient),
  ]);
}

export const useCreateAdminUser: useMutationFunctionType<
  undefined,
  { username: string; password: string },
  Users,
  Error
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["createAdminUser"],
    async (user: { username: string; password: string }) => {
      const { data } = await api.post<Users>(`${getURL("USERS")}/`, user);
      return data;
    },
    {
      ...options,
      retry: false,
      onSettled: async (...args) => {
        await refreshUserAdministration(queryClient);
        await options?.onSettled?.(...args);
      },
    },
  );
};

export const useUpdateAdminUser: useMutationFunctionType<
  undefined,
  { id: string; fields: AdminUserFields },
  Users,
  Error
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["updateAdminUser"],
    async ({ id, fields }: { id: string; fields: AdminUserFields }) => {
      const { data } = await api.patch<Users>(
        `${getURL("USERS")}/${id}`,
        fields,
      );
      return data;
    },
    {
      ...options,
      retry: false,
      onSettled: async (...args) => {
        await refreshUserAdministration(queryClient);
        await options?.onSettled?.(...args);
      },
    },
  );
};

export const useDeleteAdminUser: useMutationFunctionType<
  undefined,
  string,
  void,
  Error
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();
  return mutate(
    ["deleteAdminUser"],
    async (id: string) => {
      await api.delete(`${getURL("USERS")}/${id}`);
    },
    {
      ...options,
      retry: false,
      onSettled: async (...args) => {
        await refreshUserAdministration(queryClient);
        await options?.onSettled?.(...args);
      },
    },
  );
};
