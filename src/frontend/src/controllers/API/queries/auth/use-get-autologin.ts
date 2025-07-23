import {
  AUTO_LOGIN_MAX_RETRY_DELAY,
  AUTO_LOGIN_RETRY_DELAY,
  IS_AUTO_LOGIN,
} from "@/constants/constants";
import { AuthContext } from "@/contexts/authContext";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAuthStore from "@/stores/authStore";
import { AxiosError } from "axios";
import { useContext, useRef } from "react";
import { useQueryFunctionType, Users } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { useLogout } from "./use-post-logout";
import { IS_CLERK_AUTH } from "@/clerk/auth";

export interface AutoLoginResponse {
  frontend_timeout: number;
  auto_saving: boolean;
  auto_saving_interval: number;
  health_check_max_retries: number;
}

export const useGetAutoLogin: useQueryFunctionType<undefined, undefined> = (
  options,
) => {
  const { query } = UseRequestProcessor();
  const { login, setUserData, getUser } = useContext(AuthContext);
  const setAutoLogin = useAuthStore((state) => state.setAutoLogin);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isLoginPage = location.pathname.includes("login");
  const navigate = useCustomNavigate();
  const { mutateAsync: mutationLogout } = useLogout();
  const autoLogin = useAuthStore((state) => state.autoLogin);

  const retryCountRef = useRef(0);
  const retryTimerRef = useRef<NodeJS.Timeout | null>(null);

  async function getAutoLoginFn(): Promise<null> {
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
      const error = e as AxiosError;
      if (error.name !== "CanceledError") {
        setAutoLogin(false);
        const status = error.response?.status;
         if (status === 400 && IS_CLERK_AUTH) {
          console.log("[AutoLogin] Clerk login - skipping logout on 400");
        } else if (!isLoginPage) {
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
    const manualLoginNotAuthenticated =
      (!isAuthenticated && !IS_AUTO_LOGIN) ||
      (!isAuthenticated && autoLogin !== undefined && !autoLogin);

    const autoLoginNotAuthenticated =
      (!isAuthenticated && IS_AUTO_LOGIN) ||
      (!isAuthenticated && autoLogin !== undefined && autoLogin);

    if (manualLoginNotAuthenticated) {
      await mutationLogout();
      const currentPath = window.location.pathname;
      const isHomePath = currentPath === "/" || currentPath === "/flows";
      navigate(
        "/login" +
          (!isHomePath && !isLoginPage ? "?redirect=" + currentPath : ""),
      );
    } else if (autoLoginNotAuthenticated) {
      const retryCount = retryCountRef.current;
      const delay = Math.min(
        AUTO_LOGIN_RETRY_DELAY * Math.pow(2, retryCount),
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

  const queryResult = query(["useGetAutoLogin"], getAutoLoginFn, {
    refetchOnWindowFocus: false,
    ...options,
  });

  return queryResult;
};
