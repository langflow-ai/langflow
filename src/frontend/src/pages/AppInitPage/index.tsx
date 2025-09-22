import { useGetAutoLogin } from "@/controllers/API/queries/auth";
import { useGetConfig } from "@/controllers/API/queries/config/use-get-config";
import { useGetBasicExamplesQuery } from "@/controllers/API/queries/flows/use-get-basic-examples";
import { useGetFoldersQuery } from "@/controllers/API/queries/folders/use-get-folders";
import { useGetTagsQuery } from "@/controllers/API/queries/store";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import { useGetVersionQuery } from "@/controllers/API/queries/version";
import { CustomLoadingPage } from "@/customization/components/custom-loading-page";
import { useCustomPrimaryLoading } from "@/customization/hooks/use-custom-primary-loading";
import { useDarkStore } from "@/stores/darkStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { IS_CLERK_AUTH } from "@/clerk/auth";
import { useOrganization } from "@clerk/clerk-react";
import useAuthStore from "@/stores/authStore";

import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { LoadingPage } from "../LoadingPage";

export function AppInitPage() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const { pathname } = useLocation();
  const refreshStars = useDarkStore((state) => state.refreshStars);
  const refreshDiscordCount = useDarkStore((state) => state.refreshDiscordCount);
  const isLoading = useFlowsManagerStore((state) => state.isLoading);
  const { isFetched: isLoaded } = useCustomPrimaryLoading();
  const location = useLocation();

  const { organization, isLoaded: isOrgLoaded } = useOrganization();

  // ⛔ Skip init if on /organization OR if Clerk org not selected yet
  const shouldSkip = IS_CLERK_AUTH
    ? !isOrgLoaded || location.pathname === "/organization" || !organization?.id
    : false;

  // Skip the initialization queries when unauthenticated visitors load the
  // unauthenticated marketing landing page rendered at the root route.
  const skipAppInit = !isAuthenticated && pathname === "/";  

  const { isFetched, refetch } = useGetAutoLogin({
    enabled: isLoaded && !shouldSkip && !skipAppInit,
  });

  const { isFetched: isConfigFetched } = useGetConfig({
    enabled: isFetched && !shouldSkip && !skipAppInit,
  });

  useGetVersionQuery({ enabled: isFetched && !shouldSkip && !skipAppInit });
  useGetGlobalVariables({ enabled: isFetched && !shouldSkip && !skipAppInit });
  useGetTagsQuery({ enabled: isFetched && !shouldSkip && !skipAppInit });
  useGetFoldersQuery({ enabled: isFetched && !shouldSkip && !skipAppInit });

  const { isFetched: isExamplesFetched, refetch: refetchExamples } = useGetBasicExamplesQuery({
    enabled: !shouldSkip && !skipAppInit,
  });

  useEffect(() => {
    if (skipAppInit) {
      return;
    }
    if (isFetched && !shouldSkip) {
      refreshStars();
      refreshDiscordCount();
    }

    if (isConfigFetched && !shouldSkip) {
      refetch();
      refetchExamples();
    }
  }, [isFetched, isConfigFetched, shouldSkip, skipAppInit]);

  if (skipAppInit) {
    return <Outlet />;
  }

  return (
    //need parent component with width and height
    <>
      {isLoaded ? (
        (isLoading || (!isFetched && !shouldSkip) || (!isExamplesFetched && !shouldSkip)) && (
          <LoadingPage overlay />
        )
      ) : (
        <CustomLoadingPage />
      )}
      {(isFetched && isExamplesFetched) || shouldSkip ? <Outlet /> : null}
    </>
  );
}
