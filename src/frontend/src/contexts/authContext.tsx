import { ClerkSessionSync } from "@/components/ClerkSessionSync";
import {
  LANGFLOW_ACCESS_TOKEN,
  LANGFLOW_API_TOKEN,
  LANGFLOW_AUTO_LOGIN_OPTION,
  LANGFLOW_REFRESH_TOKEN,
} from "@/constants/constants";
import { useClerkAccessToken } from "@/controllers/API/clerk-access-token";
import { CLERK_AUTH_ENABLED } from "@/controllers/API/helpers/constants";
import { useGetUserData } from "@/controllers/API/queries/auth";
import { useGetGlobalVariablesMutation } from "@/controllers/API/queries/variables/use-get-mutation-global-variables";
import useAuthStore from "@/stores/authStore";
import { setLocalStorage } from "@/utils/local-storage-util";
import { useClerk, useUser } from "@clerk/clerk-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { Cookies } from "react-cookie";
import { useStoreStore } from "../stores/storeStore";
import { Users } from "../types/api";
import { AuthContextType } from "../types/contexts/auth";

const initialValue: AuthContextType = {
  accessToken: null,
  login: () => {},
  userData: null,
  setUserData: () => {},
  authenticationErrorCount: 0,
  setApiKey: () => {},
  apiKey: null,
  storeApiKey: () => {},
  getUser: () => {},
  logout: () => {},
};

export const AuthContext = createContext<AuthContextType>(initialValue);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const cookies = new Cookies();
  const [accessToken, setAccessToken] = useState<string | null>(
    cookies.get(LANGFLOW_ACCESS_TOKEN) ?? null,
  );
  const [userData, setUserData] = useState<Users | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(
    cookies.get(LANGFLOW_API_TOKEN) ?? null,
  );

  const checkHasStore = useStoreStore((s) => s.checkHasStore);
  const fetchApiData = useStoreStore((s) => s.fetchApiData);
  const setIsAuthenticated = useAuthStore((s) => s.setIsAuthenticated);

  const { mutate: whoAmIMutate } = useGetUserData();
  const { mutate: getGlobalsMutate } = useGetGlobalVariablesMutation();

  // Hooks from Clerk
  const { isSignedIn, isLoaded: isClerkLoaded } = useUser();
  const clerk = useClerk();

  // Our custom hook, called at top‐level:
  const getToken = useClerkAccessToken();

  useEffect(() => {
    const t = cookies.get(LANGFLOW_ACCESS_TOKEN);
    if (t) setAccessToken(t);
  }, []);

  useEffect(() => {
    const k = cookies.get(LANGFLOW_API_TOKEN);
    if (k) setApiKey(k);
  }, []);

  const getUser = useCallback(async () => {
    // 1) In Clerk mode, wait for Clerk to be ready *and* give us a JWT
    if (CLERK_AUTH_ENABLED) {
      if (!isClerkLoaded || !isSignedIn) {
        return;
      }
      const clerkJwt = await getToken();
      if (!clerkJwt) {
        console.warn("Clerk loaded but no session token, skipping /whoami");
        return;
      }
      // (Your ApiInterceptor will now attach that `clerkJwt` to the header.)
    }

    // 2) Fire your legacy /whoami
    whoAmIMutate(
      {},
      {
        onSuccess(user) {
          setUserData(user);
          useAuthStore.getState().setIsAdmin(user.is_superuser);
          checkHasStore();
          fetchApiData();
        },
        onError() {
          setUserData(null);
        },
      },
    );
  }, [
    isClerkLoaded,
    isSignedIn,
    getToken,
    whoAmIMutate,
    checkHasStore,
    fetchApiData,
  ]);

  function login(
    newAccessToken: string,
    autoLogin: string,
    refreshToken?: string,
  ) {
    cookies.set(LANGFLOW_ACCESS_TOKEN, newAccessToken, { path: "/" });
    cookies.set(LANGFLOW_AUTO_LOGIN_OPTION, autoLogin, { path: "/" });
    setLocalStorage(LANGFLOW_ACCESS_TOKEN, newAccessToken);
    if (refreshToken) {
      cookies.set(LANGFLOW_REFRESH_TOKEN, refreshToken, { path: "/" });
    }
    setAccessToken(newAccessToken);
    setIsAuthenticated(true);
    getUser();
    getGlobalsMutate({});
  }

  function logout() {
    if (CLERK_AUTH_ENABLED && clerk.signOut) {
      clerk.signOut();
    } else {
      cookies.remove(LANGFLOW_ACCESS_TOKEN);
      cookies.remove(LANGFLOW_REFRESH_TOKEN);
      cookies.remove(LANGFLOW_API_TOKEN);
      cookies.remove(LANGFLOW_AUTO_LOGIN_OPTION);
      setAccessToken(null);
      setUserData(null);
      setApiKey(null);
      setIsAuthenticated(false);
    }
  }

  function storeApiKey(key: string) {
    setApiKey(key);
  }

  return (
    <>
      {CLERK_AUTH_ENABLED && <ClerkSessionSync />}
      <AuthContext.Provider
        value={{
          accessToken,
          login,
          setUserData,
          userData,
          authenticationErrorCount: 0,
          setApiKey,
          apiKey,
          storeApiKey,
          getUser,
          logout,
        }}
      >
        {children}
      </AuthContext.Provider>
    </>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
