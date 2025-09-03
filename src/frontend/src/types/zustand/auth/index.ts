import { Users } from "@/types/api";

export interface AuthStoreType {
  setIsOrgSelected(arg0: boolean): unknown;
  isOrgSelected: any;
  isAdmin: boolean;
  isAuthenticated: boolean;
  accessToken: string | null;
  userData: Users | null;
  autoLogin: boolean | null;
  apiKey: string | null;
  authenticationErrorCount: number;

  setIsAdmin: (isAdmin: boolean) => void;
  setIsAuthenticated: (isAuthenticated: boolean) => void;
  setAccessToken: (accessToken: string | null) => void;
  setUserData: (userData: Users | null) => void;
  setAutoLogin: (autoLogin: boolean) => void;
  setApiKey: (apiKey: string | null) => void;
  setAuthenticationErrorCount: (authenticationErrorCount: number) => void;
  logout: () => Promise<void>;
  // setUserData: (userData: Users | null) => void;
  // setIsAdmin: (isAdmin: boolean) => void;
  // setApiKey: (apiKey: string | null) => void;

  // getUser: () => void;
  // login: (newAccessToken: string) => void;
  // storeApiKey: (apikey: string) => void;
}
