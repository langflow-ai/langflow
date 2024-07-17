// authStore.js
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { AuthStoreType } from "@/types/zustand/auth";
import { useNavigate } from "react-router-dom";
import Cookies from "universal-cookie";
import { create } from "zustand";
import {
  getGlobalVariables,
  getLoggedUser,
  requestLogout,
} from "../controllers/API";
import useAlertStore from "../stores/alertStore";
import { useFolderStore } from "../stores/foldersStore";
import { useGlobalVariablesStore } from "../stores/globalVariablesStore/globalVariables";
import { useStoreStore } from "../stores/storeStore";
import { Users } from "../types/api";

const cookies = new Cookies();

const useAuthStore = create<AuthStoreType>((set, get) => ({
  isAdmin: false,
  isAuthenticated: !!cookies.get("access_token_lf"),
  accessToken: cookies.get("access_token_lf") ?? null,
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
    const setAllFlows = useFlowsManagerStore.getState().setAllFlows;
    const setSelectedFolder = useFolderStore.getState().setSelectedFolder;
    cookies.remove("apikey_tkn_lflw", { path: "/" });
    set({
      isAdmin: false,
      userData: null,
      accessToken: null,
      isAuthenticated: false,
      autoLogin: false,
      apiKey: null,
    });
    setAllFlows([]);
    setSelectedFolder(null);
  },
  //   getUser: () => {
  //     const setLoading = useAlertStore.getState().setLoading;
  //     const getFoldersApi = useFolderStore.getState().getFoldersApi;
  //     const setGlobalVariables = useGlobalVariablesStore.getState().setGlobalVariables;
  //     const checkHasStore = useStoreStore.getState().checkHasStore;
  //     const fetchApiData = useStoreStore.getState().fetchApiData;

  //     getLoggedUser()
  //       .then(async (user) => {
  //         set({ userData: user, isAdmin: user.is_superuser });
  //         getFoldersApi(true, true);
  //         const res = await getGlobalVariables();
  //         setGlobalVariables(res);
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
