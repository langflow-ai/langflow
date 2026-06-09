import type { AxiosError } from "axios";
import { useContext, useRef } from "react";
import {
  AUTO_LOGIN_MAX_RETRY_DELAY,
  AUTO_LOGIN_RETRY_DELAY,
  IS_AUTO_LOGIN,
} from "@/constants/constants";
import { AuthContext } from "@/contexts/authContext";
import useAuthStore from "@/stores/authStore";
import type { Users, useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface AutoLoginResponse {
  frontend_timeout: number;
  auto_saving: boolean;
  auto_saving_interval: number;
  health_check_max_retries: number;
}

export interface AutoLoginErrorResponse {
  auto_login?: boolean;
}

export const useGetAutoLogin: useQueryFunctionType<undefined, undefined> = (
  options,
) => {
  const { query } = UseRequestProcessor();
  const { login, setUserData, getUser } = useContext(AuthContext);
  const setAutoLogin = useAuthStore((state) => state.setAutoLogin);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isLoginPage = location.pathname.includes("login");
  const autoLogin = useAuthStore((state) => state.autoLogin);

  const retryCountRef = useRef(0);
  const retryTimerRef = useRef<NodeJS.Timeout | null>(null);

  async function getAutoLoginFn(): Promise<null> {
    // Skip auto-login API call if user is already authenticated (e.g., after manual login)
    const currentAuthState = useAuthStore.getState();
    if (currentAuthState.isAuthenticated) {
      return null;
    }

    try {
      const response = await api.get<Users>(`${getURL("AUTOLOGIN")}`);
      const user = response.data;
      if (user && user["access_token"]) {
        user["refresh_token"] = "auto";
        login(user["access_token"], "auto");
        setUserData(user);
        setAutoLogin(true);
        resetTimer();
      }
    } catch (e) {
      const error = e as AxiosError<AutoLoginErrorResponse>;
      if (error.name !== "CanceledError") {
        setAutoLogin(false);
        // Don't retry if backend explicitly says auto-login is disabled
        const autoLoginDisabledByBackend =
          error.response?.data?.auto_login === false;
        if (!isLoginPage && !autoLoginDisabledByBackend) {
          await handleAutoLoginError();
        }
      }
    }
    return null;
  }

  const resetTimer = () => {
    retryCountRef.current = 0;
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
  };

  const handleAutoLoginError = async () => {
    // Get current state from store to avoid stale closure values
    const currentAuthState = useAuthStore.getState();
    const autoLoginNotAuthenticated =
      (!currentAuthState.isAuthenticated && IS_AUTO_LOGIN) ||
      (!currentAuthState.isAuthenticated &&
        currentAuthState.autoLogin !== undefined &&
        currentAuthState.autoLogin);

    if (autoLoginNotAuthenticated) {
      const retryCount = retryCountRef.current;
      const delay = Math.min(
        AUTO_LOGIN_RETRY_DELAY * 2 ** retryCount,
        AUTO_LOGIN_MAX_RETRY_DELAY,
      );

      retryCountRef.current += 1;

      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
      }

      retryTimerRef.current = setTimeout(() => {
        getAutoLoginFn();
      }, delay);
    } else {
      getUser();
    }
  };

  // Determine if query should be enabled:
  // - Don't run if user is already authenticated
  // - Respect the enabled option from caller
  // Note: We don't skip based on autoLogin === false because the frontend may
  // connect to different backends with different configurations
  const shouldBeEnabled = !isAuthenticated && (options?.enabled ?? true);

  const queryResult = query(["useGetAutoLogin"], getAutoLoginFn, {
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    staleTime: Infinity,
    retry: false,
    ...options,
    enabled: shouldBeEnabled,
  });

  return queryResult;
};
