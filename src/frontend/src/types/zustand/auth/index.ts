import type { Users } from "@/types/api";

export interface AuthStoreType {
  isAdmin: boolean;
  isAuthenticated: boolean;
  accessToken: string | null;
  userData: Users | null;
  autoLogin: boolean | null;
  apiKey: string | null;
  authenticationErrorCount: number;
  isGeneratingApiKey?: boolean;

  setIsAdmin: (isAdmin: boolean) => void;
  setIsAuthenticated: (isAuthenticated: boolean) => void;
  setAccessToken: (accessToken: string | null) => void;
  setUserData: (userData: Users | null) => void;
  setAutoLogin: (autoLogin: boolean) => void;
  setApiKey: (apiKey: string | null) => void;
  setAuthenticationErrorCount: (authenticationErrorCount: number) => void;
  setIsGeneratingApiKey?: (isGeneratingApiKey: boolean) => void;
  generateApiKey?: (name?: string) => Promise<void>;
  logout: () => Promise<void>;
  //TODO: remove comments if not used?
  // setUserData: (userData: Users | null) => void;
  // setIsAdmin: (isAdmin: boolean) => void;
  // setApiKey: (apiKey: string | null) => void;

  // getUser: () => void;
  // login: (newAccessToken: string) => void;
  // storeApiKey: (apikey: string) => void;
}
