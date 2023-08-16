import { Users } from "../api";

export type AuthContextType = {
  isAuthenticated: boolean;
  accessToken: string | null;
  refreshToken: string | null;
  login: (accessToken: string, refreshToken: string) => void;
  logout: () => void;
  refreshAccessToken: (refreshToken: string) => Promise<void>;
  userData: Users | null;
  setUserData: (userData: Users | null) => void;
  getAuthentication: () => boolean;
  authenticationErrorCount: number;
  autoLogin: boolean;
  setAutoLogin: (autoLogin: boolean) => void
};
