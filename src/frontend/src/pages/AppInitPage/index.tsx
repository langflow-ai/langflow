import { useGetAutoLogin } from "@/controllers/API/queries/auth";
import { useGetConfig } from "@/controllers/API/queries/config/use-get-config";
import { useGetVersionQuery } from "@/controllers/API/queries/version";
import { CustomLoadingPage } from "@/customization/components/custom-loading-page";
import { useCustomPrimaryLoading } from "@/customization/hooks/use-custom-primary-loading";
import { useDarkStore } from "@/stores/darkStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { LoadingPage } from "../LoadingPage";

export function AppInitPage() {
  const refreshStars = useDarkStore((state) => state.refreshStars);
  const refreshDiscordCount = useDarkStore(
    (state) => state.refreshDiscordCount,
  );
  const isLoading = useFlowsManagerStore((state) => state.isLoading);
  const location = useLocation();
  const isKeycloakCallback = location.pathname.includes("keycloak/callback");

  const { isFetched: isLoaded } = useCustomPrimaryLoading();

  // Only enable auto login if we're not in the Keycloak callback flow
  const { isFetched } = useGetAutoLogin({
    enabled: isLoaded && !isKeycloakCallback,
  });

  useGetVersionQuery({ enabled: isFetched });
  useGetConfig({ enabled: isFetched });

  useEffect(() => {
    if (isFetched) {
      refreshStars();
      refreshDiscordCount();
    }
  }, [isFetched]);

  // Always allow rendering of children when in Keycloak callback
  const shouldRenderOutlet = isFetched || isKeycloakCallback;

  return (
    //need parent component with width and height
    <>
      {isLoaded ? (
        (isLoading || (!shouldRenderOutlet && !isKeycloakCallback)) && (
          <LoadingPage overlay />
        )
      ) : (
        <CustomLoadingPage />
      )}
      {shouldRenderOutlet && <Outlet />}
    </>
  );
}
