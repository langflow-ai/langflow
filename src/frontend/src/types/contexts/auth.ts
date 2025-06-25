import { Users } from "../api";

export type AuthContextType = {
  accessToken: string | null;
  login: (
    accessToken: string,
    autoLogin: string,
    refreshToken?: string,
  ) => void;
  userData: Users | null;
  setUserData: (userData: Users | null) => void;
  authenticationErrorCount: number;
  apiKey: string | null;
  setApiKey: (apiKey: string | null) => void;
  storeApiKey: (apiKey: string) => void;
  getUser: () => void;
  logout: ()=>void
};
