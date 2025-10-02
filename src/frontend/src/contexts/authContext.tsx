import { createContext, useEffect, useState } from "react";
import { Cookies } from "react-cookie";
import {
  LANGFLOW_ACCESS_TOKEN,
  LANGFLOW_API_TOKEN,
  LANGFLOW_AUTO_LOGIN_OPTION,
  LANGFLOW_REFRESH_TOKEN,
} from "@/constants/constants";
import { useGetUserData } from "@/controllers/API/queries/auth";
import { useGetGlobalVariablesMutation } from "@/controllers/API/queries/variables/use-get-mutation-global-variables";
import useAuthStore from "@/stores/authStore";
import { setLocalStorage } from "@/utils/local-storage-util";
import { getAuthCookie, setAuthCookie } from "@/utils/utils";
import { useStoreStore } from "../stores/storeStore";
import type { Users } from "../types/api";
import type { AuthContextType } from "../types/contexts/auth";

const initialValue: AuthContextType = {
  accessToken: null,
  login: () => {},
  userData: null,
  setUserData: () => {},
  authenticationErrorCount: 0,
  setApiKey: () => {},
  apiKey: null,
  storeApiKey: () => {},
  getUser: () => {},
};

export const AuthContext = createContext<AuthContextType>(initialValue);

export function AuthProvider({ children }): React.ReactElement {
  const cookies = new Cookies();
  const [accessToken, setAccessToken] = useState<string | null>(
    getAuthCookie(cookies, LANGFLOW_ACCESS_TOKEN) ?? null,
  );
  const [userData, setUserData] = useState<Users | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(
    getAuthCookie(cookies, LANGFLOW_API_TOKEN),
  );

  const checkHasStore = useStoreStore((state) => state.checkHasStore);
  const fetchApiData = useStoreStore((state) => state.fetchApiData);
  const setIsAuthenticated = useAuthStore((state) => state.setIsAuthenticated);

  const { mutate: mutateLoggedUser } = useGetUserData();
  const { mutate: mutateGetGlobalVariables } = useGetGlobalVariablesMutation();

  useEffect(() => {
    const storedAccessToken = getAuthCookie(cookies, LANGFLOW_ACCESS_TOKEN);
    if (storedAccessToken) {
      setAccessToken(storedAccessToken);
    }
  }, []);

  useEffect(() => {
    const apiKey = getAuthCookie(cookies, LANGFLOW_API_TOKEN);
    if (apiKey) {
      setApiKey(apiKey);
    }
  }, []);

  function getUser() {
    mutateLoggedUser(
      {},
      {
        onSuccess: async (user) => {
          setUserData(user);
          const isSuperUser = user!.is_superuser;
          useAuthStore.getState().setIsAdmin(isSuperUser);
          checkHasStore();
          fetchApiData();
        },
        onError: () => {
          setUserData(null);
        },
      },
    );
  }

  function login(
    newAccessToken: string,
    autoLogin: string,
    refreshToken?: string,
  ) {
    setAuthCookie(cookies, LANGFLOW_ACCESS_TOKEN, newAccessToken);
    setAuthCookie(cookies, LANGFLOW_AUTO_LOGIN_OPTION, autoLogin);
    setLocalStorage(LANGFLOW_ACCESS_TOKEN, newAccessToken);

    if (refreshToken) {
      setAuthCookie(cookies, LANGFLOW_REFRESH_TOKEN, refreshToken);
    }
    setAccessToken(newAccessToken);
    setIsAuthenticated(true);
    getUser();
    getGlobalVariables();
  }

  function storeApiKey(apikey: string) {
    setApiKey(apikey);
  }

  function getGlobalVariables() {
    mutateGetGlobalVariables({});
  }

  return (
    // !! to convert string to boolean
    <AuthContext.Provider
      value={{
        accessToken,
        login,
        setUserData,
        userData,
        authenticationErrorCount: 0,
        setApiKey,
        apiKey,
        storeApiKey,
        getUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
