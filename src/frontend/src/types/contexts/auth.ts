import { Users } from "../api";

export type AuthContextType = {
  isAdmin: boolean;
  setIsAdmin: (isAdmin: boolean) => void;
  isAuthenticated: boolean;
  accessToken: string | null;
  login: (accessToken: string) => void;
  logout: () => Promise<void>;
  userData: Users | null;
  setUserData: (userData: Users | null) => void;
  authenticationErrorCount: number;
  autoLogin: boolean;
  setAutoLogin: (autoLogin: boolean) => void;
  apiKey: string | null;
  setApiKey: (apiKey: string | null) => void;
  storeApiKey: (apiKey: string) => void;
  getUser: () => void;
};
