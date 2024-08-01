// authStore.js
import { LANGFLOW_ACCESS_TOKEN } from "@/constants/constants";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { AuthStoreType } from "@/types/zustand/auth";
import Cookies from "universal-cookie";
import { create } from "zustand";
import { useFolderStore } from "../stores/foldersStore";

const cookies = new Cookies();
const useAuthStore = create<AuthStoreType>((set, get) => ({
  isAdmin: false,
  isAuthenticated: !!cookies.get(LANGFLOW_ACCESS_TOKEN),
  accessToken: cookies.get(LANGFLOW_ACCESS_TOKEN) ?? null,
  userData: null,
  autoLogin: false,
  apiKey: cookies.get("apikey_tkn_lflw"),
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

    window.location.href = "/login";
  },
  //   getUser: () => {
  //     const setLoading = useAlertStore.getState().setLoading;
  //     const getFoldersApi = useFolderStore.getState().getFoldersApi;
  //     const checkHasStore = useStoreStore.getState().checkHasStore;
  //     const fetchApiData = useStoreStore.getState().fetchApiData;

  //     getLoggedUser()
  //       .then(async (user) => {
  //         set({ userData: user, isAdmin: user.is_superuser });
  //         getFoldersApi(true, true);
  //         checkHasStore();
  //         fetchApiData();
  //       })
  //       .catch((error) => {
  //         setLoading(false);
  //       });
  //   },

  //   login: (newAccessToken) => {
  //     set({ accessToken: newAccessToken, isAuthenticated: true });
  //     get().getUser();
  //   },

  //   storeApiKey: (apikey) => {
  //     cookies.set('apikey_tkn_lflw', apikey, { path: '/' });
  //     set({ apiKey: apikey });
  //   },
}));

export default useAuthStore;
