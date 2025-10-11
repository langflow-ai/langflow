import { createContext, useEffect, useState } from "react";
import { Cookies } from "react-cookie";
import {
  AI_STUDIO_ACCESS_TOKEN,
  AI_STUDIO_API_TOKEN,
  AI_STUDIO_AUTO_LOGIN_OPTION,
  AI_STUDIO_REFRESH_TOKEN,
} from "@/constants/constants";
import { useGetUserData } from "@/controllers/API/queries/auth";
import { useGetGlobalVariablesMutation } from "@/controllers/API/queries/variables/use-get-mutation-global-variables";
import useAuthStore from "@/stores/authStore";
import { setLocalStorage } from "@/utils/local-storage-util";
import { getAuthCookie, setAuthCookie } from "@/utils/utils";
import { envConfig } from "@/config/env";
import KeycloakService from "@/services/keycloak";
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
    getAuthCookie(cookies, AI_STUDIO_ACCESS_TOKEN) ?? null,
  );
  const [userData, setUserData] = useState<Users | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(
    getAuthCookie(cookies, AI_STUDIO_API_TOKEN),
  );
  const [keycloakInitialized, setKeycloakInitialized] = useState(false);

  const checkHasStore = useStoreStore((state) => state.checkHasStore);
  const fetchApiData = useStoreStore((state) => state.fetchApiData);
  const setIsAuthenticated = useAuthStore((state) => state.setIsAuthenticated);

  const { mutate: mutateLoggedUser } = useGetUserData();
  const { mutate: mutateGetGlobalVariables } = useGetGlobalVariablesMutation();

  // Initialize Keycloak if enabled
  useEffect(() => {
    const initializeKeycloak = async () => {
      if (envConfig.keycloakEnabled && envConfig.keycloakUrl && envConfig.keycloakRealm && envConfig.keycloakClientId) {
        try {
          const keycloakService = KeycloakService.getInstance();
          const authenticated = await keycloakService.initialize({
            url: envConfig.keycloakUrl,
            realm: envConfig.keycloakRealm,
            clientId: envConfig.keycloakClientId,
          });

          if (authenticated) {
            const token = keycloakService.getToken();
            if (token) {
              // Store Keycloak token using AI Studio pattern
              setAuthCookie(cookies, AI_STUDIO_ACCESS_TOKEN, token);
              setLocalStorage(AI_STUDIO_ACCESS_TOKEN, token);
              setAccessToken(token);
              setIsAuthenticated(true);
              getUser();
            }
          }

          setKeycloakInitialized(true);
        } catch (error) {
          console.error("Failed to initialize Keycloak:", error);
          setKeycloakInitialized(true);
        }
      } else {
        setKeycloakInitialized(true);
      }
    };

    initializeKeycloak();
  }, []);

  useEffect(() => {
    const storedAccessToken = getAuthCookie(cookies, AI_STUDIO_ACCESS_TOKEN);
    if (storedAccessToken) {
      setAccessToken(storedAccessToken);
    }
  }, []);

  useEffect(() => {
    const apiKey = getAuthCookie(cookies, AI_STUDIO_API_TOKEN);
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
    // Check if Keycloak is enabled
    if (envConfig.keycloakEnabled) {
      // For Keycloak, redirect to Keycloak login
      const keycloakService = KeycloakService.getInstance();
      keycloakService.login().catch(console.error);
      return;
    }

    // Traditional login flow
    setAuthCookie(cookies, AI_STUDIO_ACCESS_TOKEN, newAccessToken);
    setAuthCookie(cookies, AI_STUDIO_AUTO_LOGIN_OPTION, autoLogin);
    setLocalStorage(AI_STUDIO_ACCESS_TOKEN, newAccessToken);

    if (refreshToken) {
      setAuthCookie(cookies, AI_STUDIO_REFRESH_TOKEN, refreshToken);
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
