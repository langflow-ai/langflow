import {
  LANGFLOW_ACCESS_TOKEN,
  LANGFLOW_API_TOKEN,
  LANGFLOW_AUTO_LOGIN_OPTION,
} from "@/constants/constants";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { createContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Cookies from "universal-cookie";
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
import { AuthContextType } from "../types/contexts/auth";

const initialValue: AuthContextType = {
  isAdmin: false,
  setIsAdmin: () => false,
  isAuthenticated: false,
  accessToken: null,
  login: () => {},
  logout: () => new Promise(() => {}),
  userData: null,
  setUserData: () => {},
  authenticationErrorCount: 0,
  autoLogin: false,
  setAutoLogin: () => {},
  setApiKey: () => {},
  apiKey: null,
  storeApiKey: () => {},
  getUser: () => {},
};

export const AuthContext = createContext<AuthContextType>(initialValue);

export function AuthProvider({ children }): React.ReactElement {
  const navigate = useNavigate();
  const cookies = new Cookies();
  const [accessToken, setAccessToken] = useState<string | null>(
    cookies.get(LANGFLOW_ACCESS_TOKEN) ?? null,
  );
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(
    !!cookies.get(LANGFLOW_ACCESS_TOKEN),
  );
  const [isAdmin, setIsAdmin] = useState<boolean>(false);
  const [userData, setUserData] = useState<Users | null>(null);
  const [autoLogin, setAutoLogin] = useState<boolean>(false);
  const setLoading = useAlertStore((state) => state.setLoading);
  const [apiKey, setApiKey] = useState<string | null>(
    cookies.get(LANGFLOW_API_TOKEN),
  );

  const getFoldersApi = useFolderStore((state) => state.getFoldersApi);
  const setGlobalVariables = useGlobalVariablesStore(
    (state) => state.setGlobalVariables,
  );
  const checkHasStore = useStoreStore((state) => state.checkHasStore);
  const fetchApiData = useStoreStore((state) => state.fetchApiData);
  const setAllFlows = useFlowsManagerStore((state) => state.setAllFlows);
  const setSelectedFolder = useFolderStore((state) => state.setSelectedFolder);

  useEffect(() => {
    const storedAccessToken = cookies.get(LANGFLOW_ACCESS_TOKEN);
    if (storedAccessToken) {
      setAccessToken(storedAccessToken);
    }
  }, []);

  useEffect(() => {
    const apiKey = cookies.get(LANGFLOW_API_TOKEN);
    if (apiKey) {
      setApiKey(apiKey);
    }
  }, []);

  function getUser() {
    getLoggedUser()
      .then(async (user) => {
        setUserData(user);
        const isSuperUser = user!.is_superuser;
        setIsAdmin(isSuperUser);
        getFoldersApi(true, true);
        const res = await getGlobalVariables();
        setGlobalVariables(res);
        checkHasStore();
        fetchApiData();
      })
      .catch((error) => {
        setLoading(false);
      });
  }

  function login(newAccessToken: string, autoLogin: string) {
    cookies.set(LANGFLOW_AUTO_LOGIN_OPTION, autoLogin, { path: "/" });
    setAccessToken(newAccessToken);
    setIsAuthenticated(true);
    getUser();
  }

  async function logout() {
    if (autoLogin) {
      return;
    }
    try {
      await requestLogout();
      cookies.remove(LANGFLOW_API_TOKEN, { path: "/" });
      cookies.remove(LANGFLOW_AUTO_LOGIN_OPTION, { path: "/" });
      setIsAdmin(false);
      setUserData(null);
      setAccessToken(null);
      setIsAuthenticated(false);
      setAllFlows([]);
      setSelectedFolder(null);
      navigate("/login");
      useFlowsManagerStore.setState({ isLoading: false });
    } catch (error) {
      console.error(error);
      throw error;
    }
  }

  function storeApiKey(apikey: string) {
    cookies.set(LANGFLOW_API_TOKEN, apikey, { path: "/" });
    setApiKey(apikey);
  }

  return (
    // !! to convert string to boolean
    <AuthContext.Provider
      value={{
        isAdmin,
        setIsAdmin,
        isAuthenticated,
        accessToken,
        login,
        logout,
        setUserData,
        userData,
        authenticationErrorCount: 0,
        setAutoLogin,
        autoLogin,
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
