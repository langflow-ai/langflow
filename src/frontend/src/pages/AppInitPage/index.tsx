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
import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import { LoadingPage } from "../LoadingPage";

export function AppInitPage() {
  const refreshStars = useDarkStore((state) => state.refreshStars);
  const refreshDiscordCount = useDarkStore(
    (state) => state.refreshDiscordCount,
  );
  const isLoading = useFlowsManagerStore((state) => state.isLoading);

  const { isFetched: isLoaded } = useCustomPrimaryLoading();

  const { isFetched, refetch } = useGetAutoLogin({ enabled: isLoaded });
  useGetVersionQuery({ enabled: isFetched });
  const { isFetched: isConfigFetched } = useGetConfig({ enabled: isFetched });
  useGetGlobalVariables({ enabled: isFetched });
  useGetTagsQuery({ enabled: isFetched });
  useGetFoldersQuery({ enabled: isFetched });
  const { isFetched: isExamplesFetched, refetch: refetchExamples } =
    useGetBasicExamplesQuery();

  useEffect(() => {
    if (isFetched) {
      refreshStars();
      refreshDiscordCount();
    }

    if (isConfigFetched) {
      refetch();
      refetchExamples();
    }
  }, [isFetched, isConfigFetched]);

  return (
    //need parent component with width and height
    <>
      {isLoaded ? (
        (isLoading || !isFetched || !isExamplesFetched) && (
          <LoadingPage overlay />
        )
      ) : (
        <CustomLoadingPage />
      )}
      {isFetched && isExamplesFetched && <Outlet />}
    </>
  );
}
