import type { ReactNode } from "react";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import { LoadingPage } from "@/pages/LoadingPage";
import useAuthStore from "@/stores/authStore";
import { useUserRoles } from "@/hooks/useUserRoles";

interface ProtectedRoleRouteProps {
  children: ReactNode;
  requiredRoles?: string[];
  requireAny?: boolean; // If true, user needs ANY of the roles. If false, needs ALL roles.
  fallbackPath?: string;
}

/**
 * Route guard that checks if the user has the required role(s).
 *
 * @param children - The component to render if authorized
 * @param requiredRoles - Array of role names required to access the route
 * @param requireAny - If true, user needs at least one of the roles. If false, needs all roles.
 * @param fallbackPath - Path to redirect to if unauthorized (defaults to "/")
 */
export const ProtectedRoleRoute = ({
  children,
  requiredRoles = [],
  requireAny = true,
  fallbackPath = "/",
}: ProtectedRoleRouteProps) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const { userRoles, isLoading, hasRole } = useUserRoles();

  // Show loading while checking authentication or fetching roles
  if (!isAuthenticated || isLoading || userRoles.length === 0) {
    return <LoadingPage />;
  }

  // If no required roles specified, allow access
  if (requiredRoles.length === 0) {
    return <>{children}</>;
  }

  // Check if user has required role(s)
  const hasRequiredRole = requireAny
    ? requiredRoles.some((role) => hasRole(role))
    : requiredRoles.every((role) => hasRole(role));

  if (!hasRequiredRole) {
    return <CustomNavigate to={fallbackPath} replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoleRoute;
