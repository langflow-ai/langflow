import { useContext, useEffect } from "react";
import {
  IS_AUTO_LOGIN,
  AI_STUDIO_ACCESS_TOKEN_EXPIRE_SECONDS,
  AI_STUDIO_ACCESS_TOKEN_EXPIRE_SECONDS_ENV,
} from "@/constants/constants";
import { useRefreshAccessToken } from "@/controllers/API/queries/auth";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import useAuthStore from "@/stores/authStore";
import { AuthContext } from "@/contexts/authContext";

export const ProtectedRoute = ({ children }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const { mutate: mutateRefresh } = useRefreshAccessToken();
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const isAutoLoginEnv = IS_AUTO_LOGIN;
  const testMockAutoLogin = sessionStorage.getItem("testMockAutoLogin");
  const { keycloakInitializing } = useContext(AuthContext);

  // Wait for Keycloak initialization before checking authentication
  // This prevents race condition where ProtectedRoute checks auth before Keycloak init completes
  const shouldRedirect =
    !keycloakInitializing &&
    !isAuthenticated &&
    autoLogin !== undefined &&
    (!autoLogin || !isAutoLoginEnv);

  useEffect(() => {
    const envRefreshTime = AI_STUDIO_ACCESS_TOKEN_EXPIRE_SECONDS_ENV;
    const automaticRefreshTime = AI_STUDIO_ACCESS_TOKEN_EXPIRE_SECONDS;

    const accessTokenTimer = isNaN(envRefreshTime)
      ? automaticRefreshTime
      : envRefreshTime;

    const intervalFunction = () => {
      mutateRefresh();
    };

    if (autoLogin !== undefined && !autoLogin && isAuthenticated) {
      const intervalId = setInterval(intervalFunction, accessTokenTimer * 1000);
      intervalFunction();
      return () => clearInterval(intervalId);
    }
  }, [isAuthenticated]);

  // Show loading/nothing while Keycloak is initializing
  // This prevents premature redirect to login page
  if (keycloakInitializing) {
    return null; // or return a loading spinner component
  }

  if (shouldRedirect || testMockAutoLogin) {
    const currentPath = window.location.pathname;
    const isHomePath = currentPath === "/" || currentPath === "/flows";
    const isLoginPage = location.pathname.includes("login");
    return (
      <CustomNavigate
        to={
          "/login" +
          (!isHomePath && !isLoginPage ? "?redirect=" + currentPath : "")
        }
        replace
      />
    );
  } else {
    return children;
  }
};
