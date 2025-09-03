// authStore.js
import { LANGFLOW_ACCESS_TOKEN } from "@/constants/constants";
import { AuthStoreType } from "@/types/zustand/auth";
import { Cookies } from "react-cookie";
import { create } from "zustand";

const cookies = new Cookies();
const useAuthStore = create<AuthStoreType>((set, get) => ({
  isAdmin: false,
  isAuthenticated: !!cookies.get(LANGFLOW_ACCESS_TOKEN),
  accessToken: cookies.get(LANGFLOW_ACCESS_TOKEN) ?? null,
  userData: null,
  autoLogin: null,
  apiKey: cookies.get("apikey_tkn_lflw"),
  authenticationErrorCount: 0,
  isOrgSelected: (() => {
    try {
      // Dynamically import IS_CLERK_AUTH to avoid circular deps
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const { IS_CLERK_AUTH } = require("@/clerk/auth");
      return IS_CLERK_AUTH ? false : undefined;
    } catch {
      return undefined;
    }
  })(),

  setIsAdmin: (isAdmin) => set({ isAdmin }),
  setIsAuthenticated: (isAuthenticated) => set({ isAuthenticated }),
  setAccessToken: (accessToken) => set({ accessToken }),
  setUserData: (userData) => set({ userData }),
  setAutoLogin: (autoLogin) => set({ autoLogin }),
  setApiKey: (apiKey) => set({ apiKey }),
  setAuthenticationErrorCount: (authenticationErrorCount) =>
    set({ authenticationErrorCount }),
  setIsOrgSelected: (isOrgSelected) => set({ isOrgSelected }),

 logout: async () => {
  sessionStorage.removeItem("isOrgSelected");
  get().setIsAuthenticated(false);
  get().setIsAdmin(false);
  get().setIsOrgSelected(false);

  set({
    isAdmin: false,
    userData: null,
    accessToken: null,
    isAuthenticated: false,
    autoLogin: false,
    apiKey: null,
    isOrgSelected: false,
  });
},

}));

export default useAuthStore;
