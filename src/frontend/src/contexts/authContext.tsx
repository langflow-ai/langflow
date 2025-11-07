import { createContext, useEffect, useState } from "react";
import {
  LANGFLOW_ACCESS_TOKEN,
  LANGFLOW_API_TOKEN,
  LANGFLOW_AUTO_LOGIN_OPTION,
  LANGFLOW_REFRESH_TOKEN,
} from "@/constants/constants";
import { useGetUserData } from "@/controllers/API/queries/auth";
import { useGetGlobalVariablesMutation } from "@/controllers/API/queries/variables/use-get-mutation-global-variables";
import useAuthStore from "@/stores/authStore";
import { cookieManager } from "@/utils/cookie-manager";
import { setLocalStorage } from "@/utils/local-storage-util";
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
  clearAuthSession: () => {},
};

export const AuthContext = createContext<AuthContextType>(initialValue);

export function AuthProvider({ children }): React.ReactElement {
  const [accessToken, setAccessToken] = useState<string | null>(
    cookieManager.get(LANGFLOW_ACCESS_TOKEN) ?? null,
  );
  const [userData, setUserData] = useState<Users | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(
    cookieManager.get(LANGFLOW_API_TOKEN!) ?? null,
  );

  const checkHasStore = useStoreStore((state) => state.checkHasStore);
  const fetchApiData = useStoreStore((state) => state.fetchApiData);
  const setIsAuthenticated = useAuthStore((state) => state.setIsAuthenticated);

  const { mutate: mutateLoggedUser } = useGetUserData();
  const { mutate: mutateGetGlobalVariables } = useGetGlobalVariablesMutation();

  useEffect(() => {
    const storedAccessToken = cookieManager.get(LANGFLOW_ACCESS_TOKEN);
    if (storedAccessToken) {
      setAccessToken(storedAccessToken);
    }
  }, []);

  useEffect(() => {
    const apiKey = cookieManager.get(LANGFLOW_API_TOKEN);
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
    cookieManager.set(LANGFLOW_ACCESS_TOKEN, newAccessToken);
    cookieManager.set(LANGFLOW_AUTO_LOGIN_OPTION, autoLogin);
    setLocalStorage(LANGFLOW_ACCESS_TOKEN, newAccessToken);

    if (refreshToken) {
      cookieManager.set(LANGFLOW_REFRESH_TOKEN, refreshToken);
    }
    setAccessToken(newAccessToken);

    let userLoaded = false;
    let variablesLoaded = false;
    let retryCount = 0;
    const MAX_RETRIES = 20;

    const checkAndSetAuthenticated = () => {
      if (userLoaded && variablesLoaded) {
        setIsAuthenticated(true);
      }
    };

    const executeAuthRequests = () => {
      mutateLoggedUser(
        {},
        {
          onSuccess: async (user) => {
            setUserData(user);
            const isSuperUser = user!.is_superuser;
            useAuthStore.getState().setIsAdmin(isSuperUser);
            checkHasStore();
            fetchApiData();
            userLoaded = true;
            checkAndSetAuthenticated();
          },
          onError: () => {
            setUserData(null);
            userLoaded = true;
            checkAndSetAuthenticated();
          },
        },
      );

      mutateGetGlobalVariables(
        {},
        {
          onSettled: () => {
            variablesLoaded = true;
            checkAndSetAuthenticated();
          },
        },
      );
    };

    // Verify token is available in browser cookies before proceeding
    // This prevents race condition where browser hasn't processed cookies yet
    const verifyAndProceed = () => {
      const storedToken = cookieManager.get(LANGFLOW_ACCESS_TOKEN);
      if (storedToken) {
        executeAuthRequests();
      } else if (retryCount < MAX_RETRIES) {
        retryCount++;
        setTimeout(verifyAndProceed, 50);
      } else {
        // Proceed anyway after timeout to avoid blocking login
        executeAuthRequests();
      }
    };

    setTimeout(verifyAndProceed, 50);
  }

  function storeApiKey(apikey: string) {
    setApiKey(apikey);
  }

  function clearAuthSession() {
    cookieManager.clearAuthCookies();
    localStorage.removeItem(LANGFLOW_ACCESS_TOKEN);
    localStorage.removeItem(LANGFLOW_API_TOKEN);
    localStorage.removeItem(LANGFLOW_REFRESH_TOKEN);
    setAccessToken(null);
    setApiKey(null);
    setUserData(null);
    setIsAuthenticated(false);
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
        clearAuthSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
