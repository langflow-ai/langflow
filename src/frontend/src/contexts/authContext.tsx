import { createContext, useEffect, useState } from "react";
import { AuthContextType, userData } from "../types/contexts/auth";
import { LoginType } from "../types/api";
import { api } from "../controllers/API/api";

const initialValue: AuthContextType = {
  isAuthenticated: false,
  accessToken: null,
  refreshToken: null,
  login: () => {},
  logout: () => {},
  refreshAccessToken: () => Promise.resolve(),
  userData: null,
  setUserData: () => {},
};

export const AuthContext = createContext<AuthContextType>(initialValue);

export function AuthProvider({ children }): React.ReactElement {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [userData, setUserData] = useState<userData>(null);

  useEffect(() => {
    const storedAccessToken = localStorage.getItem("access_token");
    if (storedAccessToken) {
      setAccessToken(storedAccessToken);
    }
  }, []);

  function login(newAccessToken: string, refreshToken: string) {
    localStorage.setItem("access_token", newAccessToken);
    setAccessToken(newAccessToken);

    localStorage.setItem("refresh_token", refreshToken);
    setRefreshToken(refreshToken);

    setIsAuthenticated(true);
  }

  function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
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
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
