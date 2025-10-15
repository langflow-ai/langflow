// authStore.js

import { Cookies } from "react-cookie";
import { create } from "zustand";
import {
  AI_STUDIO_ACCESS_TOKEN,
  AI_STUDIO_API_TOKEN,
} from "@/constants/constants";
import { envConfig } from "@/config/env";
import type { AuthStoreType } from "@/types/zustand/auth";

const cookies = new Cookies();

// Clear traditional auth cookies if Keycloak is enabled
const initializeAuthState = () => {
  if (envConfig.keycloakEnabled) {
    // Clear any existing traditional auth cookies when Keycloak is enabled
    cookies.remove(AI_STUDIO_ACCESS_TOKEN);
    cookies.remove(AI_STUDIO_API_TOKEN);
    localStorage.removeItem(AI_STUDIO_ACCESS_TOKEN);
    return {
      isAuthenticated: false,
      accessToken: null,
      apiKey: null,
    };
  }

  // Traditional auth initialization
  return {
    isAuthenticated: !!cookies.get(AI_STUDIO_ACCESS_TOKEN),
    accessToken: cookies.get(AI_STUDIO_ACCESS_TOKEN) ?? null,
    apiKey: cookies.get(AI_STUDIO_API_TOKEN),
  };
};

const initialAuthState = initializeAuthState();

const useAuthStore = create<AuthStoreType>((set, get) => ({
  isAdmin: false,
  isAuthenticated: initialAuthState.isAuthenticated,
  accessToken: initialAuthState.accessToken,
  userData: null,
  autoLogin: null,
  apiKey: initialAuthState.apiKey,
  authenticationErrorCount: 0,

  setIsAdmin: (isAdmin) => set({ isAdmin }),
  setIsAuthenticated: (isAuthenticated) => set({ isAuthenticated }),
  setAccessToken: (accessToken) => set({ accessToken }),
  setUserData: (userData) => set({ userData }),
  setAutoLogin: (autoLogin) => set({ autoLogin }),
  setApiKey: (apiKey) => set({ apiKey }),
  setAuthenticationErrorCount: (authenticationErrorCount) =>
    set({ authenticationErrorCount }),

  logout: async () => {
    get().setIsAuthenticated(false);
    get().setIsAdmin(false);

    // Clear cookies and localStorage
    cookies.remove(AI_STUDIO_ACCESS_TOKEN);
    cookies.remove(AI_STUDIO_API_TOKEN);
    localStorage.removeItem(AI_STUDIO_ACCESS_TOKEN);

    set({
      isAdmin: false,
      userData: null,
      accessToken: null,
      isAuthenticated: false,
      autoLogin: false,
      apiKey: null,
    });
  },
}));

export default useAuthStore;
