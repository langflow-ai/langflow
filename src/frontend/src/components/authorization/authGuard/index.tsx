import {
  IS_AUTO_LOGIN,
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS,
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV,
} from "@/constants/constants";
import { useRefreshAccessToken } from "@/controllers/API/queries/auth";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import useAuthStore from "@/stores/authStore";
import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useOrganization, useAuth as useClerkAuth } from "@clerk/clerk-react";

export const ProtectedRoute = ({ children }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const isOrgSelectedStore = useAuthStore((state) => state.isOrgSelected);
  const isOrgSelected =
    isOrgSelectedStore || sessionStorage.getItem("isOrgSelected") === "true";
  const { mutate: mutateRefresh } = useRefreshAccessToken();
  const testMockAutoLogin = sessionStorage.getItem("testMockAutoLogin");

  // Clerk values
  const { organization, isLoaded: isOrgLoaded } = useOrganization();
  const { isSignedIn } = useClerkAuth();
  const orgId = organization?.id;

  
  // Get current path
  const location = useLocation();
  const currentPath = location.pathname;
  const isLoginPage = currentPath.includes("login");
  const isOrgPage = currentPath.includes("organization");
  const isRootPage = currentPath === "/";
  const isFlowsPage = currentPath.includes("/flows");

  // 1️⃣ Redirect to login if not authenticated
  const shouldRedirectToLogin =
    isOrgLoaded &&
    (!isAuthenticated || !isSignedIn) &&
    autoLogin !== undefined &&
    (!autoLogin || !IS_AUTO_LOGIN);

  // 2️⃣ Redirect to organization selection if signed in but no org yet
  const shouldRedirectToOrg =
    isOrgLoaded &&
    isAuthenticated &&
    isSignedIn &&
    !isOrgSelected &&
    !isOrgPage &&
    !isLoginPage;

  // ✅ 3️⃣ Redirect "/" to "/flows" ONLY if fully authenticated and org selected
  const shouldRedirectHome =
    isOrgLoaded &&
    isAuthenticated &&
    isSignedIn &&
    isOrgSelected &&
    isRootPage;

  // 🔄 Setup token refresh
  useEffect(() => {
    const refreshTime = isNaN(LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV)
      ? LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS
      : LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV;

    if (autoLogin !== undefined && !autoLogin && isAuthenticated) {
      const intervalId = setInterval(() => {
        mutateRefresh();
      }, refreshTime * 1000);

      return () => {
        clearInterval(intervalId);
      };
    }
  }, [isAuthenticated, autoLogin, mutateRefresh]);

  if (!isOrgLoaded || autoLogin === undefined) {
    return null;
  }

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

  // 🔹 Redirect to /organization
  if (shouldRedirectToOrg) {
    return <CustomNavigate to="/organization" replace />;
  }

  // 🔹 Redirect "/" to "/flows" only if safe
  if (shouldRedirectHome) {
    return <CustomNavigate to="/flows" replace />;
  }

  // ✅ Otherwise render the page
  return children;
};
