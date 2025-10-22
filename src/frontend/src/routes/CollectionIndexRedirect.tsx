import { IS_CLERK_AUTH } from "@/clerk/auth";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import authStore from "@/stores/authStore";
import { lazy, Suspense } from "react";
import { LoadingPage } from "@/pages/LoadingPage";

const LandingPage = lazy(() => import("@/pages/LandingPage"));

const hasSelectedOrganization = () =>
  typeof window !== "undefined" &&
  sessionStorage.getItem("isOrgSelected") === "true";

export function CollectionIndexRedirect() {
  const { isAuthenticated, isOrgSelected } = authStore((state) => ({
    isAuthenticated: state.isAuthenticated,
    isOrgSelected: state.isOrgSelected,
  }));

  const organizationChosen =
    Boolean(isOrgSelected) ||
    (IS_CLERK_AUTH && hasSelectedOrganization());

  // Unauthenticated users: Show the public Landing Page
  if (!isAuthenticated) {
    return (
      <Suspense fallback={<LoadingPage />}>
        <LandingPage />
      </Suspense>
    );
  }

  // Authenticated but no org selected: go to organization selection
  if (IS_CLERK_AUTH && isAuthenticated && !organizationChosen) {
    return <CustomNavigate replace to="/organization" />;
  }

  // Authenticated with org: go to flows
  return <CustomNavigate replace to="flows" />;
}
