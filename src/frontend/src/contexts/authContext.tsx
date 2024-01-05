import { createContext, useEffect, useState } from "react";
import Cookies from "universal-cookie";
import { autoLogin as autoLoginApi, getLoggedUser } from "../controllers/API";
import useAlertStore from "../stores/alertStore";
import { Users } from "../types/api";
import { AuthContextType } from "../types/contexts/auth";

const initialValue: AuthContextType = {
  isAdmin: false,
  setIsAdmin: () => false,
  isAuthenticated: false,
  accessToken: null,
  refreshToken: null,
  login: () => {},
  logout: () => {},
  userData: null,
  setUserData: () => {},
  authenticationErrorCount: 0,
  autoLogin: false,
  setAutoLogin: () => {},
  setApiKey: () => {},
  apiKey: null,
  storeApiKey: () => {},
};

export const AuthContext = createContext<AuthContextType>(initialValue);

export function AuthProvider({ children }): React.ReactElement {
  const cookies = new Cookies();
  const [accessToken, setAccessToken] = useState<string | null>(
    cookies.get("access_tkn_lflw")
  );
  const [refreshToken, setRefreshToken] = useState<string | null>(
    cookies.get("refresh_tkn_lflw")
  );
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(
    cookies.get("refresh_tkn_lflw") && cookies.get("access_tkn_lflw")
  );
  const [isAdmin, setIsAdmin] = useState<boolean>(false);
  const [userData, setUserData] = useState<Users | null>(null);
  const [autoLogin, setAutoLogin] = useState<boolean>(false);
  const setLoading = useAlertStore((state) => state.setLoading);
  const [apiKey, setApiKey] = useState<string | null>(
    cookies.get("apikey_tkn_lflw")
  );

  useEffect(() => {
    const storedAccessToken = cookies.get("access_tkn_lflw");
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

  useEffect(() => {
    const isLoginPage = location.pathname.includes("login");

    autoLoginApi()
      .then((user) => {
        if (user && user["access_token"]) {
          user["refresh_token"] = "auto";
          login(user["access_token"], user["refresh_token"]);
          setUserData(user);
          setAutoLogin(true);
          setLoading(false);
        }
      })
      .catch((error) => {
        setAutoLogin(false);
        if (isAuthenticated && !isLoginPage) {
          getUser();
        } else {
          setLoading(false);
        }
      });
  }, [setUserData, setLoading, autoLogin, setIsAdmin]);

  function getUser(){
    getLoggedUser()
      .then((user) => {
        setUserData(user);
        setLoading(false);
        const isSuperUser = user!.is_superuser;
        setIsAdmin(isSuperUser);
      })
      .catch((error) => {
        console.log("auth context");
        setLoading(false);
      });
  }

  function login(newAccessToken: string, refreshToken: string) {
    cookies.set("access_tkn_lflw", newAccessToken, { path: "/" });
    cookies.set("refresh_tkn_lflw", refreshToken, { path: "/" });
    setAccessToken(newAccessToken);
    setRefreshToken(refreshToken);
    setIsAuthenticated(true);
    setTimeout(() => {getUser();}, 500)
    
  }

  function logout() {
    cookies.remove("access_tkn_lflw", { path: "/" });
    cookies.remove("refresh_tkn_lflw", { path: "/" });
    cookies.remove("apikey_tkn_lflw", { path: "/" });
    setIsAdmin(false);
    setUserData(null);
    setAccessToken(null);
    setRefreshToken(null);
    setIsAuthenticated(false);
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
        refreshToken,
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
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
