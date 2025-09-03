import {
  IS_AUTO_LOGIN,
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS,
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV,
} from "@/constants/constants";
import { useRefreshAccessToken } from "@/controllers/API/queries/auth";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import useAuthStore from "@/stores/authStore";
import { useEffect } from "react";
import { useOrganization, useAuth as useClerkAuth } from "@clerk/clerk-react";

export const ProtectedRoute = ({ children }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const isOrgSelected = useAuthStore((state) => state.isOrgSelected);
  const { mutate: mutateRefresh } = useRefreshAccessToken();
  const testMockAutoLogin = sessionStorage.getItem("testMockAutoLogin");

  // Clerk values
  const { organization, isLoaded: isOrgLoaded } = useOrganization();
  const { isSignedIn } = useClerkAuth();
  const orgId = organization?.id;

  
  // Get current path
  const currentPath = window.location.pathname;
  const isLoginPage = currentPath.includes("login");
  const isOrgPage = currentPath.includes("organization");
  const isRootPage = currentPath === "/";
  const isFlowsPage = currentPath.includes("/flows");
  
  console.log("[ProtectedRoute] Render", {
  isAuthenticated,
    autoLogin,
    isOrgSelected,
    orgId,
    currentPath
  });
  /**
   * 1️⃣ Redirect unauthenticated users to /login
   */
  const shouldRedirectToLogin =
    isOrgLoaded &&
    (!isAuthenticated || !isSignedIn) &&
    autoLogin !== undefined &&
    (!autoLogin || !IS_AUTO_LOGIN);

  /**
   * 2️⃣ Always redirect to /organization if:
   * - User is authenticated
   * - Clerk session exists
   * - No org selected yet (manual step required)
   * - Not already on /organization or /login
   */
  const shouldRedirectToOrg =
    isOrgLoaded &&
    isAuthenticated &&
    isSignedIn &&
    !isOrgSelected &&
    !isOrgPage &&
    !isLoginPage;

  /**
   * 3️⃣ If user lands on "/" but already selected org → go to flows
   */
  const shouldRedirectHome =
    isOrgLoaded &&
    isAuthenticated &&
    isSignedIn &&
    isOrgSelected &&
    isRootPage;

  /**
   * 🔄 Setup token auto-refresh only if authenticated
   */
  useEffect(() => {
    const refreshTime = isNaN(LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV)
      ? LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS
      : LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV;

    if (autoLogin !== undefined && !autoLogin && isAuthenticated) {
      console.log("[ProtectedRoute] Setting token refresh interval", { refreshTime });

      const intervalId = setInterval(() => {
        console.log("[ProtectedRoute] Refreshing access token");
        mutateRefresh();
      }, refreshTime * 1000);

      return () => {
        console.log("[ProtectedRoute] Clearing token refresh interval");
        clearInterval(intervalId);
      };
    }
  }, [isAuthenticated, autoLogin, mutateRefresh]);

  /**
   * 🔹 Force redirect to login if unauthenticated
   */
  if (shouldRedirectToLogin || testMockAutoLogin) {
    const isHomePath = isRootPage || isFlowsPage;
    return (
      <CustomNavigate
        to={
          "/login" +
          (!isHomePath && !isLoginPage ? `?redirect=${currentPath}` : "")
        }
        replace
      />
    );
  }

  /**
   * 🔹 Force redirect to organization page for org selection
   */
  if (shouldRedirectToOrg) {
    return <CustomNavigate to="/organization" replace />;
  }

  /**
   * 🔹 Redirect "/" to "/flows" if org already selected
   */
  if (shouldRedirectHome) {
    return <CustomNavigate to="/flows" replace />;
  }

  /**
   * ✅ Otherwise, render the children
   */
  return children;
};
