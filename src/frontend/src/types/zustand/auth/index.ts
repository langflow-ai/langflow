import type { Users } from "@/types/api";
import type { AuthUserData } from "@/types/auth";

export interface AuthStoreType {
  isAdmin: boolean;
  isAuthenticated: boolean;
  accessToken: string | null;
  userData: Users | null;
  autoLogin: boolean | null;
  apiKey: string | null;
  authenticationErrorCount: number;

  // Role-based access control
  userRoles: string[];
  authUserData: AuthUserData | null;

  setIsAdmin: (isAdmin: boolean) => void;
  setIsAuthenticated: (isAuthenticated: boolean) => void;
  setAccessToken: (accessToken: string | null) => void;
  setUserData: (userData: Users | null) => void;
  setAutoLogin: (autoLogin: boolean) => void;
  setApiKey: (apiKey: string | null) => void;
  setAuthenticationErrorCount: (authenticationErrorCount: number) => void;
  logout: () => Promise<void>;

  // Role-based access control methods
  setUserRoles: (roles: string[]) => void;
  setAuthUserData: (authUserData: AuthUserData | null) => void;
  hasRole: (roleName: string) => boolean;
  isMarketplaceAdmin: () => boolean;
  isAgentDeveloper: () => boolean;
}
