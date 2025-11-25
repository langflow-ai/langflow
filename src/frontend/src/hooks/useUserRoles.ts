import { useEffect } from "react";
import { useGetUserRoles } from "@/controllers/API/queries/auth";
import useAuthStore from "@/stores/authStore";
import { USER_ROLES } from "@/types/auth";

/**
 * Hook to fetch and manage user roles.
 * Automatically fetches roles when user is authenticated and stores them in the auth store.
 */
export const useUserRoles = () => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const setUserRoles = useAuthStore((state) => state.setUserRoles);
  const setAuthUserData = useAuthStore((state) => state.setAuthUserData);
  const userRoles = useAuthStore((state) => state.userRoles);
  const authUserData = useAuthStore((state) => state.authUserData);

  const { data, isLoading, isError, error, refetch } = useGetUserRoles(
    isAuthenticated && userRoles.length === 0,
  );

  useEffect(() => {
    if (data?.data) {
      // Extract role names from the response
      const roleNames = data.data.roles.map((role) => role.name);
      setUserRoles(roleNames);
      setAuthUserData(data.data);
    }
  }, [data, setUserRoles, setAuthUserData]);

  const hasRole = (roleName: string): boolean => {
    return userRoles.includes(roleName);
  };

  const isMarketplaceAdmin = (): boolean => {
    return hasRole(USER_ROLES.MARKETPLACE_ADMIN);
  };

  const isAgentDeveloper = (): boolean => {
    return hasRole(USER_ROLES.AGENT_DEVELOPER);
  };

  const isSuperAdmin = (): boolean => {
    return hasRole(USER_ROLES.SUPER_ADMIN);
  };

  return {
    userRoles,
    authUserData,
    isLoading,
    isError,
    error,
    refetch,
    hasRole,
    isMarketplaceAdmin,
    isAgentDeveloper,
    isSuperAdmin,
  };
};

export default useUserRoles;
