import { useContext, useEffect, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import { AuthContext } from "@/contexts/authContext";
import {
  useGetAuthSession,
  useGetAutoLogin,
} from "@/controllers/API/queries/auth";
import useAuthStore from "@/stores/authStore";
import { LoadingPage } from "@/pages/LoadingPage";

export function PlaygroundAuthGate({
  children,
}: {
  children: React.ReactNode;
}) {
  const { id } = useParams();
  const { setUserData, storeApiKey } = useContext(AuthContext);
  const setIsAuthenticated = useAuthStore((state) => state.setIsAuthenticated);
  const setIsAdmin = useAuthStore((state) => state.setIsAdmin);
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const [sessionProcessed, setSessionProcessed] = useState(false);

  const { data: sessionData, isFetched: isSessionFetched } =
    useGetAuthSession();
  const { isFetched: isAutoLoginFetched } = useGetAutoLogin();

  useEffect(() => {
    if (!isSessionFetched) return;

    if (sessionData?.authenticated && sessionData.user) {
      setUserData(sessionData.user);
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

  const isAuthCheckComplete =
    (isAutoLoginFetched || isAuthenticated) && sessionProcessed;

  if (!isAuthCheckComplete) {
    return <LoadingPage />;
  }

  if (autoLogin === false && !isAuthenticated) {
    const currentPath = `/playground/${id}/`;
    return <Navigate to={`/login?redirect=${currentPath}`} replace />;
  }

  return <>{children}</>;
}
