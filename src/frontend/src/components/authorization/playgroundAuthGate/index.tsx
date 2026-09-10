import { useContext, useEffect, useState } from "react";
import { AuthContext } from "@/contexts/authContext";
import {
  useGetAuthSession,
  useGetAutoLogin,
} from "@/controllers/API/queries/auth";
import { LoadingPage } from "@/pages/LoadingPage";
import useAuthStore from "@/stores/authStore";
import type { Users } from "@/types/api";
import { computePlaygroundAuthState } from "./authState";

export { computePlaygroundAuthState };
export type { PlaygroundAuthState } from "./authState";

export function PlaygroundAuthGate({
  children,
}: {
  children: React.ReactNode;
}) {
  const { setUserData, storeApiKey } = useContext(AuthContext);
  const setIsAuthenticated = useAuthStore((state) => state.setIsAuthenticated);
  const setIsAdmin = useAuthStore((state) => state.setIsAdmin);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const [sessionProcessed, setSessionProcessed] = useState(false);

  const { data: sessionData, isFetched: isSessionFetched } =
    useGetAuthSession();
  const { isFetched: isAutoLoginFetched } = useGetAutoLogin();

  useEffect(() => {
    if (!isSessionFetched) return;

    if (sessionData?.authenticated && sessionData.user) {
      // Set in both AuthContext (for components using useContext) and Zustand
      // store (for hooks like useGetFlowId and isAuthenticatedPlayground).
      // Both must be kept in sync — clearing one without the other causes stale state.
      const user = sessionData.user as Users;
      setUserData(user);
      useAuthStore.getState().setUserData(user);
      setIsAuthenticated(true);
      setIsAdmin(sessionData.user.is_superuser || false);
      if (sessionData.store_api_key) {
        storeApiKey(sessionData.store_api_key);
      }
    } else if (sessionData && !sessionData.authenticated) {
      setIsAuthenticated(false);
    }
    setSessionProcessed(true);
  }, [sessionData, isSessionFetched]);

  const authState = computePlaygroundAuthState({
    isAuthenticated,
    isAutoLoginFetched,
    isSessionProcessed: sessionProcessed,
  });

  if (authState === "loading") {
    return <LoadingPage />;
  }

  return <>{children}</>;
}
