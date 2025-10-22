import { CustomNavigate } from "@/customization/components/custom-navigate";
import useAuthStore from "@/stores/authStore";

/**
 * CatchAllRedirect component handles unknown/invalid routes by redirecting based on authentication status.
 * 
 * Authenticated users: Redirects to /flows (main workspace)
 * Unauthenticated users: Redirects to / (landing page)
 */
export function CatchAllRedirect() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const autoLogin = useAuthStore((state) => state.autoLogin);

  // Determine if user is truly authenticated (either logged in or auto-login enabled)
  const isUserAuthenticated = isAuthenticated || autoLogin === true;

  // Redirect authenticated users to /flows, unauthenticated users to landing page "/"
  const redirectTo = isUserAuthenticated ? "/flows" : "/";

  return <CustomNavigate replace to={redirectTo} />;
}
