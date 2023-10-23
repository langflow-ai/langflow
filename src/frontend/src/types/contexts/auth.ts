import { Users } from "../api";

export type AuthContextType = {
  isAdmin: boolean;
  setIsAdmin: (isAdmin: boolean) => void;
  isAuthenticated: boolean;
  accessToken: string | null;
  refreshToken: string | null;
  login: (accessToken: string, refreshToken: string) => void;
  logout: () => void;
  userData: Users | null;
  setUserData: (userData: Users | null) => void;
  getAuthentication: () => boolean;
  authenticationErrorCount: number;
  autoLogin: boolean;
  setAutoLogin: (autoLogin: boolean) => void;
  apiKey: string | null;
  setApiKey: (apiKey: string | null) => void;
  storeApiKey: (apiKey: string) => void;
};
