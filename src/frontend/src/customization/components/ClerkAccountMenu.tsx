import { UserButton, useClerk } from "@clerk/clerk-react";
import { IS_CLERK_AUTH, useLogout } from "@/clerk/auth";
import { LogOut, Users } from "lucide-react";
import { AccountMenu } from "@/components/core/appHeaderComponent/components/AccountMenu";

export function ClerkAccountMenu() {
  const { mutate: mutationLogout } = useLogout();
  const { openOrganizationProfile } = useClerk();

  const handleLogout = () => {
    mutationLogout();
  };

  const handleOpenOrgProfile = () => {
    if (openOrganizationProfile) {
      openOrganizationProfile();
    }
  };

  return IS_CLERK_AUTH ? (
    <div className="flex items-center gap-x-3">
      <UserButton
        appearance={{
          elements: {
            avatarBox: "h-6 w-6",
            userButtonPopoverActionButton__signOut: "hidden",
          },
        }}
      >
        <UserButton.MenuItems>
          <UserButton.Action
            label="Members"
            labelIcon={<Users className="h-4 w-4" />}
            onClick={handleOpenOrgProfile}
          />
          <UserButton.Action
            label="Sign out"
            labelIcon={<LogOut className="h-4 w-4" />}
            onClick={handleLogout}
          />
        </UserButton.MenuItems>
      </UserButton>
      <AccountMenu />
    </div>
  ) : (
    <AccountMenu />
  );
}

export default ClerkAccountMenu;