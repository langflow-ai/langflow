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

import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { LoadingPage } from "../LoadingPage";

export function AppInitPage() {
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

  const { isFetched, refetch } = useGetAutoLogin({
    enabled: isLoaded && !shouldSkip,
  });

  const { isFetched: isConfigFetched } = useGetConfig({
    enabled: isFetched && !shouldSkip,
  });

  useGetVersionQuery({ enabled: isFetched && !shouldSkip });
  useGetGlobalVariables({ enabled: isFetched && !shouldSkip });
  useGetTagsQuery({ enabled: isFetched && !shouldSkip });
  useGetFoldersQuery({ enabled: isFetched && !shouldSkip });

  const { isFetched: isExamplesFetched, refetch: refetchExamples } = useGetBasicExamplesQuery({
    enabled: !shouldSkip,
  });

  useEffect(() => {
    if (isFetched && !shouldSkip) {
      refreshStars();
      refreshDiscordCount();
    }

    if (isConfigFetched && !shouldSkip) {
      refetch();
      refetchExamples();
    }
  }, [isFetched, isConfigFetched, shouldSkip]);

  return (
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
