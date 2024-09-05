import {
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS,
  LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS_ENV,
} from "@/constants/constants";
import { useRefreshAccessToken } from "@/controllers/API/queries/auth";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import useAuthStore from "@/stores/authStore";
import { useEffect } from "react";

export const ProtectedRoute = ({ children }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const { mutate: mutateRefresh } = useRefreshAccessToken();
  const autoLogin = useAuthStore((state) => state.autoLogin);

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
  if (!isAuthenticated && autoLogin !== undefined && !autoLogin) {
    return <CustomNavigate to="/login" replace />;
  } else {
    return children;
  }
};
