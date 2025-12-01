import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import type { AuthUserResponse } from "@/types/auth";

/**
 * Fetches user roles and data from the auth service.
 * Uses the authorization token to identify the user.
 */
export const useGetUserRoles = (enabled: boolean = true) => {
  const getUserRoles = async (): Promise<AuthUserResponse> => {
    const response = await api.get<AuthUserResponse>("/api/v1/auth/user/email");
    return response.data;
  };

  return useQuery({
    queryKey: ["userRoles"],
    queryFn: getUserRoles,
    enabled,
    staleTime: 1 * 60 * 1000, // 1 minutes
    retry: 1,
  });
};
