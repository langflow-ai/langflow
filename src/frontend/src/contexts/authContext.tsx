import { createContext, useEffect, useState } from "react";
import { AuthContextType, userData } from "../types/contexts/auth";
import { LoginType } from "../types/api";
import { api } from "../controllers/API/api";
import Cookies from 'universal-cookie';

const initialValue: AuthContextType = {
  isAuthenticated: false,
  accessToken: null,
  refreshToken: null,
  login: () => {},
  logout: () => {},
  refreshAccessToken: () => Promise.resolve(),
  userData: null,
  setUserData: () => {},
  getAuthentication: () => false,
};

export const AuthContext = createContext<AuthContextType>(initialValue);

export function AuthProvider({ children }): React.ReactElement {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [userData, setUserData] = useState<userData>(null);
  const cookies = new Cookies();

  useEffect(() => {
    const storedAccessToken = localStorage.getItem("access_token");
    if (storedAccessToken) {
      setAccessToken(storedAccessToken);
    }
  }, []);


  function getAuthentication(){
    const storedRefreshToken = cookies.get('refresh_token');
    const storedAccess = cookies.get('refresh_token');
    const auth = storedAccess && storedRefreshToken ? true : false;
    return auth;
  }

  function login(newAccessToken: string, refreshToken: string) {
    cookies.set('access_token', newAccessToken, { path: '/' });
    cookies.set('refresh_token', refreshToken, { path: '/' });
    setAccessToken(newAccessToken);
    setRefreshToken(refreshToken);
    setIsAuthenticated(true);
  }

  function logout() {
    cookies.remove('access_token');
    cookies.remove('refresh_token');
    setAccessToken(null);
    setRefreshToken(null);
    setIsAuthenticated(false);

  }

  async function refreshAccessToken(refreshToken: string) {
    try {
      const response = await fetch("/api/refresh-token", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refreshToken }),
      });

      if (response.ok) {
        const data = await response.json();
        login(data.accessToken, refreshToken);
      } else {
        logout();
      }
    } catch (error) {
      logout();
    }
  }
 

  return (
    // !! to convert string to boolean
    <AuthContext.Provider
      value={{
        isAuthenticated: !!accessToken,
        accessToken,
        refreshToken,
        login,
        logout,
        refreshAccessToken,
        setUserData,
        userData,
        getAuthentication
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
