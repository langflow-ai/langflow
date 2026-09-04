import { useEffect } from "react";
import {
  IS_AUTO_LOGIN,
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS,
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV,
} from "@/constants/constants";
import { useRefreshAccessToken } from "@/controllers/API/queries/auth";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import useAuthStore from "@/stores/authStore";

export const ProtectedRoute = ({ children }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const { mutate: mutateRefresh } = useRefreshAccessToken();
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const isAutoLoginEnv = IS_AUTO_LOGIN;
  const testMockAutoLogin = sessionStorage.getItem("testMockAutoLogin");

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

    // Proactively refresh the access token before it expires for any
    // authenticated session — manual login AND auto-login. Auto-login tokens
    // are now short-lived (ACCESS_TOKEN_EXPIRE_SECONDS) and ``/auto_login`` sets
    // a ``refresh_token_lf`` cookie, so the session must refresh transparently
    // via ``/refresh`` instead of relying on a long-lived token. Without this, a
    // tab left open past the token lifetime would 401 with no client-side
    // recovery until a full page reload.
    if (autoLogin !== undefined && isAuthenticated) {
      const intervalId = setInterval(intervalFunction, accessTokenTimer * 1000);
      // Manual sessions refresh once on mount to validate the cookie session.
      // Auto-login just minted a fresh token via ``/auto_login``, so skip the
      // redundant immediate refresh and let the interval keep it alive.
      if (!autoLogin) {
        intervalFunction();
      }
      return () => clearInterval(intervalId);
    }
  }, [isAuthenticated, autoLogin]);

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
