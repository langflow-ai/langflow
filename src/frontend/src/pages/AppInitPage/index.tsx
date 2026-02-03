import { useContext, useEffect, useMemo } from "react";
import { Outlet } from "react-router-dom";
import { AuthContext } from "@/contexts/authContext";
import {
  useGetAuthSession,
  useGetAutoLogin,
} from "@/controllers/API/queries/auth";
import { useGetConfig } from "@/controllers/API/queries/config/use-get-config";
import { useGetBasicExamplesQuery } from "@/controllers/API/queries/flows/use-get-basic-examples";
import { useGetFoldersQuery } from "@/controllers/API/queries/folders/use-get-folders";
import { useGetTagsQuery } from "@/controllers/API/queries/store";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import { useGetVersionQuery } from "@/controllers/API/queries/version";
import { CustomLoadingPage } from "@/customization/components/custom-loading-page";
import { useCustomPrimaryLoading } from "@/customization/hooks/use-custom-primary-loading";
import useAuthStore from "@/stores/authStore";
import { useDarkStore } from "@/stores/darkStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { LoadingPage } from "../LoadingPage";

export function AppInitPage() {
  const refreshStars = useDarkStore((state) => state.refreshStars);
  const refreshDiscordCount = useDarkStore(
    (state) => state.refreshDiscordCount,
  );
  const isLoading = useFlowsManagerStore((state) => state.isLoading);
  const { setUserData, storeApiKey } = useContext(AuthContext);
  const setIsAuthenticated = useAuthStore((state) => state.setIsAuthenticated);
  const setIsAdmin = useAuthStore((state) => state.setIsAdmin);
  const autoLogin = useAuthStore((state) => state.autoLogin);

  const { isFetched: isLoaded } = useCustomPrimaryLoading();

  // Validate session on app init to restore auth state from HttpOnly cookies
  const { data: sessionData, isFetched: isSessionFetched } = useGetAuthSession({
    enabled: isLoaded,
  });

  const { isFetched } = useGetAutoLogin({ enabled: isLoaded });
  useGetVersionQuery({ enabled: isFetched });
  const { isFetched: isConfigFetched } = useGetConfig({ enabled: isFetched });
  useGetGlobalVariables({ enabled: isFetched });
  useGetTagsQuery({ enabled: isFetched });
  useGetFoldersQuery({ enabled: isFetched });
  const { isFetched: isExamplesFetched, refetch: refetchExamples } =
    useGetBasicExamplesQuery();

  // Update auth state when session data is available
  useEffect(() => {
    if (sessionData?.authenticated && sessionData.user) {
      setUserData(sessionData.user);
      setIsAuthenticated(true);
      setIsAdmin(sessionData.user.is_superuser || false);
      if (sessionData.store_api_key) {
        storeApiKey(sessionData.store_api_key);
      }
    } else if (sessionData && !sessionData.authenticated) {
      // Explicitly not authenticated
      setIsAuthenticated(false);
    }
  }, [sessionData]);

  useEffect(() => {
    if (isFetched) {
      refreshStars();
      refreshDiscordCount();
    }

    if (isConfigFetched) {
      refetchExamples();
    }
  }, [isFetched, isConfigFetched]);

  const isSessionReady = useMemo(() => {
    if (autoLogin === true) {
      return true;
    }
    if (autoLogin === false) {
      return isSessionFetched;
    }
    return false;
  }, [autoLogin, isSessionFetched]);

  const isReady = isFetched && isExamplesFetched && isSessionReady;

  return (
    <>
      {isLoaded ? (
        (isLoading || !isReady) && <LoadingPage overlay />
      ) : (
        <CustomLoadingPage />
      )}
      {isReady && <Outlet />}
    </>
  );
}
