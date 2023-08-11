export type AuthContextType = {
  isAuthenticated: boolean;
  accessToken: string | null;
  refreshToken: string | null;
  login: (accessToken: string, refreshToken: string) => void;
  logout: () => void;
  refreshAccessToken: (refreshToken: string) => Promise<void>;
  userData: userData | null;
  setUserData: (userData: userData | null) => void;
  getAuthentication: () => boolean;
};

export type userData = {
  id: string;
  name: string;
  email: string;
  role: string;
};
