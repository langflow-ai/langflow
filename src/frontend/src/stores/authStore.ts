// authStore.js

import { create } from "zustand";
import {
  LANGFLOW_ACCESS_TOKEN,
  LANGFLOW_API_TOKEN,
} from "@/constants/constants";
import useGetCookieAuth from "@/shared/hooks/use-get-cookie-auth";
import type { AuthStoreType } from "@/types/zustand/auth";

const useAuthStore = create<AuthStoreType>((set, get) => ({
  isAdmin: false,
  isAuthenticated: !!useGetCookieAuth(LANGFLOW_ACCESS_TOKEN),
  accessToken: useGetCookieAuth(LANGFLOW_ACCESS_TOKEN) ?? null,
  userData: null,
  autoLogin: null,
  apiKey: useGetCookieAuth(LANGFLOW_API_TOKEN),
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
