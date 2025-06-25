import {
  IS_AUTO_LOGIN,
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS,
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV,
} from "@/constants/constants";
import { useRefreshAccessToken } from "@/controllers/API/queries/auth";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import useAuthStore from "@/stores/authStore";
import { useAuth } from "@clerk/clerk-react";
import { useEffect } from "react";

// ✅ Clerk auth flag
const IS_CLERK_ENABLED = import.meta.env.VITE_CLERK_AUTH_ENABLED === "true";

export const ProtectedRoute = ({ children }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const { mutate: mutateRefresh } = useRefreshAccessToken();
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const isAutoLoginEnv = IS_AUTO_LOGIN;
  const testMockAutoLogin = sessionStorage.getItem("testMockAutoLogin");
  const { isSignedIn } = useAuth();
  // ✅ Skip all legacy auth logic if Clerk is active
  if (IS_CLERK_ENABLED) {
    if (isSignedIn) {
      return children;
    }
  }

  const shouldRedirect =
    !isAuthenticated &&
    autoLogin !== undefined &&
    (!autoLogin || !isAutoLoginEnv);

  useEffect(() => {
    const envRefreshTime = LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV;
    const automaticRefreshTime = LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS;
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
  }

  return children;
};
