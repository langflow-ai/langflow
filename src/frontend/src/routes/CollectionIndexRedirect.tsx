import { IS_CLERK_AUTH } from "@/clerk/auth";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import authStore from "@/stores/authStore";

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

  if (IS_CLERK_AUTH && isAuthenticated && !organizationChosen) {
    return <CustomNavigate replace to="/organization" />;
  }

  return <CustomNavigate replace to="flows" />;
}
