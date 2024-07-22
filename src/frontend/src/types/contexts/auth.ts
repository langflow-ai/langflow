import { Users } from "../api";

export type AuthContextType = {
  isAdmin: boolean;
  setIsAdmin: (isAdmin: boolean) => void;
  accessToken: string | null;
  login: (accessToken: string, autoLogin: string) => void;
  logout: () => Promise<void>;
  userData: Users | null;
  setUserData: (userData: Users | null) => void;
  authenticationErrorCount: number;
  apiKey: string | null;
  setApiKey: (apiKey: string | null) => void;
  storeApiKey: (apiKey: string) => void;
  getUser: () => void;
};
