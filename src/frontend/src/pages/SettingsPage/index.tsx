import { Outlet, type To } from "react-router-dom";
import type { ReactNode } from "react";
import SideBarButtonsComponent, { type SidebarNavItem } from "@/components/core/sidebarComponent";
import { SidebarProvider } from "@/components/ui/sidebar";
import { CustomStoreSidebar } from "@/customization/components/custom-store-sidebar";
import {
  ENABLE_DATASTAX_LANGFLOW,
  ENABLE_LANGFLOW_STORE,
  ENABLE_PROFILE_ICONS,
} from "@/customization/feature-flags";
import useAuthStore from "@/stores/authStore";
import { useStoreStore } from "@/stores/storeStore";
import ForwardedIconComponent from "../../components/common/genericIconComponent";
import PageLayout from "../../components/common/pageLayout";
import { useClerk, useOrganization } from "@clerk/clerk-react";
import { IS_CLERK_AUTH } from "@/clerk/auth";

type SettingsPageBaseProps = {
  headerActions?: ReactNode;
  additionalNavItems?: SidebarNavItem[];
};

const SettingsPageBase = ({
  headerActions,
  additionalNavItems = [],
}: SettingsPageBaseProps) => {
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const hasStore = useStoreStore((state) => state.hasStore);

  // Hides the General settings if there is nothing to show
  const showGeneralSettings = ENABLE_PROFILE_ICONS || hasStore || !autoLogin;

  // Build sidebar items in the intended order
  const sidebarNavItems: SidebarNavItem[] = [];

  sidebarNavItems.push(
    {
      title: "MCP Servers",
      href: "/settings/mcp-servers",
      icon: (
        <ForwardedIconComponent
          name="Mcp"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
    {
      title: "Global Variables",
      href: "/settings/global-variables",
      icon: (
        <ForwardedIconComponent
          name="Globe"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },

    {
      title: "Shortcuts",
      href: "/settings/shortcuts",
      icon: (
        <ForwardedIconComponent
          name="Keyboard"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
    {
      title: "Messages",
      href: "/settings/messages",
      icon: (
        <ForwardedIconComponent
          name="MessagesSquare"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
  );

  // TODO: Remove this on cleanup
  if (!ENABLE_DATASTAX_LANGFLOW) {
    const langflowItems = CustomStoreSidebar(true, ENABLE_LANGFLOW_STORE);
    sidebarNavItems.splice(2, 0, ...langflowItems);
  }

  // Append Clerk-related items at the end
  sidebarNavItems.push(...additionalNavItems);

  return (
    <PageLayout
      backTo={-1 as To}
      title="Settings"
      description="Manage the general settings for Visual AI Agents Builder."
    >
      <SidebarProvider width="15rem" defaultOpen={false}>
        <SideBarButtonsComponent items={sidebarNavItems} />
        <main className="flex flex-1 overflow-hidden">
          <div className="flex flex-1 flex-col overflow-x-hidden pt-1">
            <Outlet />
          </div>
        </main>
      </SidebarProvider>
    </PageLayout>
  );
};

const SettingsPageWithClerk = () => {
  const { openUserProfile, openOrganizationProfile } = useClerk();
  const { organization, isLoaded: isOrganizationLoaded } = useOrganization();

  const canManageMembers = Boolean(
    isOrganizationLoaded && organization?.id && openOrganizationProfile,
  );

  const handleManageAccount = () => {
    openUserProfile?.();
  };

  const handleManageMembers = () => {
    if (canManageMembers) {
      openOrganizationProfile?.();
    }
  };

  const clerkNavItems: SidebarNavItem[] = [
    {
      title: "Manage Account",
      icon: (
        <ForwardedIconComponent
          name="User"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
      onClick: handleManageAccount,
    },
    {
      title: "Members",
      icon: (
        <ForwardedIconComponent
          name="Users"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
      onClick: handleManageMembers,
      disabled: !canManageMembers,
    },
    {
      title: "Debugging",
      href: "/settings/debugging",
      icon: (
        <ForwardedIconComponent
          name="Bug"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
  ];

  // Pass Clerk items so they show at the bottom
  return <SettingsPageBase additionalNavItems={clerkNavItems} />;
};

const SettingsPageWithoutClerk = () => <SettingsPageBase />;

export default function SettingsPage(): JSX.Element {
  if (IS_CLERK_AUTH) {
    return <SettingsPageWithClerk />;
  }

  return <SettingsPageWithoutClerk />;
}
