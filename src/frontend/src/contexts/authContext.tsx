import { createContext, useEffect, useState } from "react";
import { AuthContextType, userData } from "../types/contexts/auth";

const initialValue: AuthContextType = {
  isAuthenticated: false,
  accessToken: null,
  login: () => {},
  logout: () => {},
  refreshAccessToken: () => Promise.resolve(),
  userData: null,
  setUserData: () => {},
};

const AuthContext = createContext<AuthContextType>(initialValue);

export function AuthProvider({ children }): React.ReactElement {
  const [accessToken, setAccessToken] = useState<string | null>(null);
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
    // Store refreshToken if needed
  }

  function logout() {
    localStorage.removeItem("access_token");
    // Clear refreshToken if used
    setAccessToken(null);
  }

  async function refreshAccessToken(refreshToken: string) {
    try {
      // Call your API to refresh the access token using the refresh token
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
