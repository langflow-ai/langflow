import { IS_CLERK_AUTH } from "@/clerk/auth";
import { useOrganization } from "@clerk/clerk-react";
import { Building2 } from "lucide-react";

/**
 * Component that displays the organization name when Clerk authentication is enabled.
 * Shows the organization name with an icon, only visible when authenticated via Clerk.
 */
export function OrganizationDisplay() {
  const { organization, isLoaded } = useOrganization();

  // Don't render if Clerk auth is not enabled
  if (!IS_CLERK_AUTH) {
    return null;
  }

  // Don't render if organization data is not loaded yet
  if (!isLoaded) {
    return null;
  }

  // Don't render if no organization is selected
  if (!organization) {
    return null;
  }

  return (
    <div
      className="flex items-center gap-1.5 rounded-md bg-muted/30 px-2.5 py-1 text-xs transition-colors hover:bg-muted/50"
      data-testid="organization-display"
    >
      <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
      <span className="font-medium text-foreground/90 max-w-[200px] truncate">
        {organization.name}
      </span>
    </div>
  );
}

export default OrganizationDisplay;
