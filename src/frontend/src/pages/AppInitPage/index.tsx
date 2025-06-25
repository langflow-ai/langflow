// src/frontend/src/pages/AppInitPage/index.tsx
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
import { LoadingPage } from "../LoadingPage";

import useAuthStore from "@/stores/authStore";
import { useDarkStore } from "@/stores/darkStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";

import { useUser } from "@clerk/clerk-react";
import { useAuth } from "@/contexts/authContext";

const IS_CLERK_ENABLED = import.meta.env.VITE_CLERK_AUTH_ENABLED === "true";

export function AppInitPage() {
  const navigate = useNavigate();

  const refreshStars = useDarkStore((s) => s.refreshStars);
  const refreshDiscordCount = useDarkStore((s) => s.refreshDiscordCount);
  const isLoading = useFlowsManagerStore((s) => s.isLoading);
  const { isFetched: isLoaded } = useCustomPrimaryLoading();

  const { isSignedIn, isLoaded: isClerkLoaded } = useUser();
  const setAutoLogin = useAuthStore((s) => s.setAutoLogin);
  const { getUser, userData } = useAuth();

  // 1️⃣ Clerk Routing
  useEffect(() => {
    if (!IS_CLERK_ENABLED) return;
    if (!isClerkLoaded) return;

    if (isSignedIn) {
      navigate("/flows");
    } else {
      navigate("/login");
    }
  }, [isClerkLoaded, isSignedIn, navigate]);

  useEffect(() => {
    if (IS_CLERK_ENABLED && isClerkLoaded && isSignedIn && !userData) {
      getUser();
    }
  }, [isClerkLoaded, isSignedIn, userData]);

  // 2️⃣ Legacy Auth
  const { isFetched: autoFetched, refetch: refetchAuto } = useGetAutoLogin({
    enabled: !IS_CLERK_ENABLED && isLoaded,
  });

  useGetVersionQuery({ enabled: IS_CLERK_ENABLED ? isSignedIn && isClerkLoaded : autoFetched, });
  const { isFetched: configFetched } = useGetConfig({
    enabled: IS_CLERK_ENABLED ? isSignedIn && isClerkLoaded : autoFetched,
  });
  useGetGlobalVariables({ enabled: IS_CLERK_ENABLED ? isSignedIn && isClerkLoaded : autoFetched, });
  useGetTagsQuery({ enabled: IS_CLERK_ENABLED ? isSignedIn && isClerkLoaded : autoFetched, });
  useGetFoldersQuery({ enabled: IS_CLERK_ENABLED ? isSignedIn && isClerkLoaded : autoFetched, });

  const {
    isFetched: examplesFetched,
    refetch: refetchExamples,
  } = useGetBasicExamplesQuery({
    enabled: IS_CLERK_ENABLED ? isSignedIn && isClerkLoaded : autoFetched,
  });

  useEffect(() => {
    if (!IS_CLERK_ENABLED && configFetched) {
      setAutoLogin(true);
      refetchAuto();
      refetchExamples();
      refreshStars();
      refreshDiscordCount();
    }
  }, [
    IS_CLERK_ENABLED,
    configFetched,
    refetchAuto,
    refetchExamples,
    refreshStars,
    refreshDiscordCount,
    setAutoLogin,
  ]);

  // 3️⃣ Loader
  const showLoader = IS_CLERK_ENABLED
    ? !isClerkLoaded
    : !autoFetched || !examplesFetched || isLoading;

  // 4️⃣ Outlet rendering
  const canRenderOutlet = IS_CLERK_ENABLED
  ? isClerkLoaded
  : autoFetched && examplesFetched;

  return (
    <>
      {showLoader && <LoadingPage overlay />}
      {canRenderOutlet && <Outlet />}
    </>
  );
}
