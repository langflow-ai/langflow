import { createContext, useContext, useEffect, useState } from "react";
import Cookies from "universal-cookie";
import { autoLogin as autoLoginApi, getLoggedUser } from "../controllers/API";
import { Users } from "../types/api";
import { AuthContextType } from "../types/contexts/auth";
import { alertContext } from "./alertContext";

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
  getAuthentication: () => false,
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
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isAdmin, setIsAdmin] = useState<boolean>(false);
  const [userData, setUserData] = useState<Users | null>(null);
  const [autoLogin, setAutoLogin] = useState<boolean>(false);
  const { setLoading } = useContext(alertContext);
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
        if (getAuthentication() && !isLoginPage) {
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
        } else {
          setLoading(false);
        }
      });
  }, [setUserData, setLoading, autoLogin, setIsAdmin]);

  function getAuthentication() {
    const storedRefreshToken = cookies.get("refresh_tkn_lflw");
    const storedAccess = cookies.get("access_tkn_lflw");
    const auth = storedAccess && storedRefreshToken ? true : false;
    return auth;
  }

  function login(newAccessToken: string, refreshToken: string) {
    cookies.set("access_tkn_lflw", newAccessToken, { path: "/" });
    cookies.set("refresh_tkn_lflw", refreshToken, { path: "/" });
    setAccessToken(newAccessToken);
    setRefreshToken(refreshToken);
    setIsAuthenticated(true);
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
        isAuthenticated: !!accessToken,
        accessToken,
        refreshToken,
        login,
        logout,
        setUserData,
        userData,
        getAuthentication,
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
