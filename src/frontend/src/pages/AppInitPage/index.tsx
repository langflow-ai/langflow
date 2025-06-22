import { useEffect } from "react";
import { Outlet, useNavigate } from "react-router-dom";

import { useGetAutoLogin } from "@/controllers/API/queries/auth";
import { useGetConfig } from "@/controllers/API/queries/config/use-get-config";
import { useGetBasicExamplesQuery } from "@/controllers/API/queries/flows/use-get-basic-examples";
import { useGetFoldersQuery } from "@/controllers/API/queries/folders/use-get-folders";
import { useGetTagsQuery } from "@/controllers/API/queries/store";
import { useGetGlobalVariables } from "@/controllers/API/queries/variables";
import { useGetVersionQuery } from "@/controllers/API/queries/version";

import { useCustomPrimaryLoading } from "@/customization/hooks/use-custom-primary-loading";
import { CustomLoadingPage } from "@/customization/components/custom-loading-page";
import { LoadingPage } from "../LoadingPage";

import useAuthStore from "@/stores/authStore";
import { useDarkStore } from "@/stores/darkStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";

import { useUser } from "@clerk/clerk-react";

const IS_CLERK_ENABLED = import.meta.env.VITE_CLERK_AUTH_ENABLED === "true";

export function AppInitPage() {
  const navigate = useNavigate();

  const refreshStars = useDarkStore((state) => state.refreshStars);
  const refreshDiscordCount = useDarkStore((state) => state.refreshDiscordCount);
  const isLoading = useFlowsManagerStore((state) => state.isLoading);
  const { isFetched: isLoaded } = useCustomPrimaryLoading();

  const { isSignedIn, isLoaded: isClerkLoaded } = useUser();
  const setAutoLogin = useAuthStore((state) => state.setAutoLogin);

  // Clerk-only logic
  useEffect(() => {
    if (IS_CLERK_ENABLED) {
      if (isClerkLoaded) {
        if (isSignedIn) {
          navigate("/flows");
        } else {
          navigate("/login");
        }
      }
    }
  }, [isClerkLoaded, isSignedIn, navigate]);

  // === Legacy auto-login ===
  const { isFetched, refetch } = useGetAutoLogin({ enabled: !IS_CLERK_ENABLED && isLoaded });
  useGetVersionQuery({ enabled: !IS_CLERK_ENABLED && isFetched });
  const { isFetched: isConfigFetched } = useGetConfig({ enabled: !IS_CLERK_ENABLED && isFetched });
  useGetGlobalVariables({ enabled: !IS_CLERK_ENABLED && isFetched });
  useGetTagsQuery({ enabled: !IS_CLERK_ENABLED && isFetched });
  useGetFoldersQuery({ enabled: !IS_CLERK_ENABLED && isFetched });

  const { isFetched: isExamplesFetched, refetch: refetchExamples } = useGetBasicExamplesQuery({
    enabled: !IS_CLERK_ENABLED || (IS_CLERK_ENABLED && isSignedIn && isClerkLoaded),
  });

  useEffect(() => {
    if (!IS_CLERK_ENABLED && isFetched) {
      refreshStars();
      refreshDiscordCount();
    }

    if (!IS_CLERK_ENABLED && isConfigFetched) {
      refetch();
      refetchExamples();
    }
  }, [isFetched, isConfigFetched]);

  const showLoader =
    !isLoaded ||
    (IS_CLERK_ENABLED
      ? !isClerkLoaded
      : isLoading || !isFetched || !isExamplesFetched);

  const canRenderOutlet =
    IS_CLERK_ENABLED ? isClerkLoaded : isFetched && isExamplesFetched;

  return (
    <>
      {showLoader ? <LoadingPage overlay /> : null}
      {canRenderOutlet && <Outlet />}
    </>
  );
}
