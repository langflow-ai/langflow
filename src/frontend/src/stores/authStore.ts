// authStore.js

import { create } from "zustand";
import {
  LANGFLOW_ACCESS_TOKEN,
  LANGFLOW_API_TOKEN,
  LANGFLOW_REFRESH_TOKEN,
} from "@/constants/constants";
import type { AuthStoreType } from "@/types/zustand/auth";
import { cookieManager, getCookiesInstance } from "@/utils/cookie-manager";

const cookies = getCookiesInstance();
const useAuthStore = create<AuthStoreType>((set, get) => ({
  isAdmin: false,
  isAuthenticated: !!cookies.get(LANGFLOW_ACCESS_TOKEN),
  accessToken: cookies.get(LANGFLOW_ACCESS_TOKEN) ?? null,
  userData: null,
  autoLogin: null,
  apiKey: cookies.get(LANGFLOW_API_TOKEN),
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
    localStorage.removeItem(LANGFLOW_ACCESS_TOKEN);
    localStorage.removeItem(LANGFLOW_API_TOKEN);
    localStorage.removeItem(LANGFLOW_REFRESH_TOKEN);

    cookieManager.clearAuthCookies();

    get().setIsAuthenticated(false);
    get().setIsAdmin(false);

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
