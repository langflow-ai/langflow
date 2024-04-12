import { createContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Cookies from "universal-cookie";
import { getLoggedUser, requestLogout } from "../controllers/API";
import useAlertStore from "../stores/alertStore";
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
    cookies.get("access_token_lf") ?? null
  );
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(
    !!cookies.get("access_token_lf")
  );
  const [isAdmin, setIsAdmin] = useState<boolean>(false);
  const [userData, setUserData] = useState<Users | null>(null);
  const [autoLogin, setAutoLogin] = useState<boolean>(false);
  const setLoading = useAlertStore((state) => state.setLoading);
  const [apiKey, setApiKey] = useState<string | null>(
    cookies.get("apikey_tkn_lflw")
  );

  useEffect(() => {
    const storedAccessToken = cookies.get("access_token_lf");
    if (storedAccessToken) {
      setAccessToken(storedAccessToken);
    }
  }, []);

  useEffect(() => {
    const apiKey = cookies.get("apikey_tkn_lflw");
    if (apiKey) {
      setApiKey(apiKey);
    }
  }, []);

  function getUser() {
    getLoggedUser()
      .then((user) => {
        setUserData(user);
        setLoading(false);
        const isSuperUser = user!.is_superuser;
        setIsAdmin(isSuperUser);
      })
      .catch((error) => {
        setLoading(false);
      });
  }

  function login(newAccessToken: string) {
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
      cookies.remove("apikey_tkn_lflw", { path: "/" });
      setIsAdmin(false);
      setUserData(null);
      setAccessToken(null);
      setIsAuthenticated(false);
      navigate("/login");
    } catch (error) {
      console.error(error);
      throw error;
    }
  }

  function storeApiKey(apikey: string) {
    cookies.set("apikey_tkn_lflw", apikey, { path: "/" });
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
