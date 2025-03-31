import { AuthContext } from "@/contexts/authContext";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAuthStore from "@/stores/authStore";
import { AxiosError } from "axios";
import { useContext } from "react";
import { useQueryFunctionType, Users } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { useLogout } from "./use-post-logout";

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

  async function getAutoLoginFn(): Promise<null> {
    try {
      const response = await api.get<Users>(`${getURL("AUTOLOGIN")}`);
      const user = response.data;
      if (user && user["access_token"]) {
        user["refresh_token"] = "auto";
        login(user["access_token"], "auto");
        setUserData(user);
        setAutoLogin(true);
      }
    } catch (e) {
      const error = e as AxiosError;
      if (error.name !== "CanceledError") {
        setAutoLogin(false);
        if (!isLoginPage) {
          if (!isAuthenticated) {
            await mutationLogout();
            const currentPath = window.location.pathname;
            const isHomePath = currentPath === "/" || currentPath === "/flows";
            navigate(
              "/login" +
                (!isHomePath && !isLoginPage ? "?redirect=" + currentPath : ""),
            );
          } else {
            getUser();
          }
        }
      }
    }
    return null;
  }

  const queryResult = query(["useGetAutoLogin"], getAutoLoginFn, {
    refetchOnWindowFocus: false,
    ...options,
  });

  return queryResult;
};
