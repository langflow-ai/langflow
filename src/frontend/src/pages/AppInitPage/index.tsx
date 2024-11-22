import { useGetAutoLogin } from "@/controllers/API/queries/auth";
import { useGetConfig } from "@/controllers/API/queries/config/use-get-config";
import { useGetBasicExamplesQuery } from "@/controllers/API/queries/flows/use-get-basic-examples";
import { useGetTypes } from "@/controllers/API/queries/flows/use-get-types";
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
  const dark = useDarkStore((state) => state.dark);
  const refreshStars = useDarkStore((state) => state.refreshStars);
  const isLoading = useFlowsManagerStore((state) => state.isLoading);

  const { isFetched: isLoaded } = useCustomPrimaryLoading();

  const { isFetched } = useGetAutoLogin({ enabled: isLoaded });
  useGetVersionQuery({ enabled: isFetched });
  useGetConfig({ enabled: isFetched });
  const { isFetched: typesLoaded } = useGetTypes({ enabled: isFetched });
  useGetGlobalVariables({ enabled: typesLoaded });
  useGetTagsQuery({ enabled: typesLoaded });
  useGetFoldersQuery({
    enabled: typesLoaded,
  });
  const { isFetched: isExamplesFetched } = useGetBasicExamplesQuery({
    enabled: typesLoaded,
  });

  useEffect(() => {
    if (isFetched) {
      refreshStars();
    }
  }, [isFetched]);

  useEffect(() => {
    if (!dark) {
      document.getElementById("body")!.classList.remove("dark");
    } else {
      document.getElementById("body")!.classList.add("dark");
    }
  }, [dark]);

  return (
    //need parent component with width and height
    <>
      {isLoaded ? (
        (isLoading || !isFetched || !isExamplesFetched || !typesLoaded) && (
          <LoadingPage overlay />
        )
      ) : (
        <CustomLoadingPage />
      )}
      {isFetched && isExamplesFetched && typesLoaded && <Outlet />}
    </>
  );
}
