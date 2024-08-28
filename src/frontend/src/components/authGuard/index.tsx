import {
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS,
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV,
  LANGFLOW_AUTO_LOGIN_OPTION,
} from "@/constants/constants";
import { useRefreshAccessToken } from "@/controllers/API/queries/auth";
import useAuthStore from "@/stores/authStore";
import { useEffect } from "react";
import { Cookies } from "react-cookie";

export const ProtectedRoute = ({ children }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const hasToken = !!localStorage.getItem(LANGFLOW_AUTO_LOGIN_OPTION);
  const logout = useAuthStore((state) => state.logout);

  const cookies = new Cookies();
  const refreshToken = cookies.get("refresh_token");
  const { mutate: mutateRefresh } = useRefreshAccessToken();

  useEffect(() => {
    const envRefreshTime = LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV;
    const automaticRefreshTime = LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS;

    const accessTokenTimer = isNaN(envRefreshTime)
      ? automaticRefreshTime
      : envRefreshTime;

    const intervalFunction = () => {
      if (isAuthenticated) {
        mutateRefresh({ refresh_token: refreshToken });
      }
    };

    const intervalId = setInterval(intervalFunction, accessTokenTimer * 1000);
    intervalFunction();

    return () => clearInterval(intervalId);
  }, [isAuthenticated]);

  if (!isAuthenticated && hasToken) {
    logout();
  } else {
    return children;
  }
};
