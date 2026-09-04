import { createContext, useState } from "react";
import {
  LANGFLOW_API_TOKEN,
  LANGFLOW_AUTO_LOGIN_OPTION,
  LANGFLOW_REFRESH_TOKEN,
} from "@/constants/constants";
import { useGetUserData } from "@/controllers/API/queries/auth";
import { useGetGlobalVariablesMutation } from "@/controllers/API/queries/variables/use-get-mutation-global-variables";
import useAuthStore from "@/stores/authStore";
import { cookieManager } from "@/utils/cookie-manager";
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
  // Authentication state is now managed via session validation
  // instead of reading cookies directly (supports HttpOnly cookies)
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [userData, setUserData] = useState<Users | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(null);

  const checkHasStore = useStoreStore((state) => state.checkHasStore);
  const fetchApiData = useStoreStore((state) => state.fetchApiData);
  const setIsAuthenticated = useAuthStore((state) => state.setIsAuthenticated);

  const { mutate: mutateLoggedUser } = useGetUserData();
  const { mutate: mutateGetGlobalVariables } = useGetGlobalVariablesMutation();

  // Session validation is now handled by components that need it
  // (e.g., via useGetAuthSession hook) rather than reading cookies here

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
    _refreshToken?: string,
  ) {
    // The server owns both token cookies so their HttpOnly attributes cannot
    // be downgraded by a JavaScript-written cookie with the same name.
    cookieManager.set(LANGFLOW_AUTO_LOGIN_OPTION, autoLogin);
    setAccessToken(newAccessToken);

    let userLoaded = false;
    let variablesLoaded = false;

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

    // Execute auth requests directly
    // Cookies are set by the server and browser handles them automatically
    executeAuthRequests();
  }

  function storeApiKey(apikey: string) {
    setApiKey(apikey);
  }

  function clearAuthSession() {
    cookieManager.clearAuthCookies();
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
