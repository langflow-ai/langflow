import { useTranslation } from "react-i18next";
import { Outlet, type To, useLocation } from "react-router-dom";
import SideBarButtonsComponent from "@/components/core/sidebarComponent";
import { SidebarProvider } from "@/components/ui/sidebar";
import { CustomStoreSidebar } from "@/customization/components/custom-store-sidebar";
import {
  ENABLE_DATASTAX_LANGFLOW,
  ENABLE_PROFILE_ICONS,
} from "@/customization/feature-flags";
import { useDocumentTitle } from "@/hooks/use-document-title";
import useAuthStore from "@/stores/authStore";
import { useStoreStore } from "@/stores/storeStore";
import { useUtilityStore } from "@/stores/utilityStore";
import ForwardedIconComponent from "../../components/common/genericIconComponent";
import PageLayout from "../../components/common/pageLayout";
export default function SettingsPage(): JSX.Element {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const isSuperuser = Boolean(
    useAuthStore((state) => state.userData)?.is_superuser,
  );
  const hasStore = useStoreStore((state) => state.hasStore);
  const migrationEnabled = useUtilityStore(
    (state) => state.featureFlags.instance_migration === true,
  );

  // Hides the General settings if there is nothing to show
  const showGeneralSettings = ENABLE_PROFILE_ICONS || hasStore || !autoLogin;

  const sidebarNavItems: {
    href?: string;
    title: string;
    icon: React.ReactNode;
  }[] = [];

  if (showGeneralSettings) {
    sidebarNavItems.push({
      title: t("settings.nav.general"),
      href: "/settings/general",
      icon: (
        <ForwardedIconComponent
          name="SlidersHorizontal"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    });
  }

  sidebarNavItems.push(
    {
      title: t("settings.nav.mcpServers"),
      href: "/settings/mcp-servers",
      icon: (
        <ForwardedIconComponent
          name="Mcp"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
    {
      title: t("settings.nav.mcpClient"),
      href: "/settings/mcp-client",
      icon: (
        <ForwardedIconComponent
          name="Terminal"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
    {
      title: t("settings.nav.connections"),
      href: "/settings/connections",
      icon: (
        <ForwardedIconComponent
          name="Plug"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
    {
      title: t("settings.nav.globalVariables"),
      href: "/settings/global-variables",
      icon: (
        <ForwardedIconComponent
          name="Globe"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
    {
      title: t("settings.nav.modelProviders"),
      href: "/settings/model-providers",
      icon: (
        <ForwardedIconComponent
          name="BrainCircuit"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
    {
      title: t("settings.nav.dbProviders"),
      href: "/settings/db-providers",
      icon: (
        <ForwardedIconComponent
          name="Database"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },

    {
      title: t("settings.nav.shortcuts"),
      href: "/settings/shortcuts",
      icon: (
        <ForwardedIconComponent
          name="Keyboard"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
    {
      title: t("settings.nav.messages"),
      href: "/settings/messages",
      icon: (
        <ForwardedIconComponent
          name="MessagesSquare"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    },
  );

  if (isSuperuser && migrationEnabled) {
    sidebarNavItems.push({
      title: t("settings.nav.migration"),
      href: "/settings/migration",
      icon: (
        <ForwardedIconComponent
          name="ArrowRightLeft"
          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
        />
      ),
    });
  }

  // TODO: Remove this on cleanup
  if (!ENABLE_DATASTAX_LANGFLOW) {
    const langflowItems = CustomStoreSidebar(true);
    sidebarNavItems.splice(2, 0, ...langflowItems);
  }

  // Every settings section shares this shell, so the tab title has to name the
  // open section rather than just "Settings" (WCAG 2.4.2).
  const activeNavItem = sidebarNavItems.find(
    (item) => item.href && pathname.startsWith(item.href),
  );
  useDocumentTitle(activeNavItem?.title ?? t("settings.title"));

  return (
    <PageLayout
      backTo={-1 as To}
      title={t("settings.title")}
      description={t("settings.description")}
    >
      <SidebarProvider width="15rem" defaultOpen={false}>
        <SideBarButtonsComponent items={sidebarNavItems} />
        {/* Overflow is clipped. Neither box scrolls, and a box that hides its overflow is what a sticky element inside a page sticks to. */}
        <main className="flex min-w-0 flex-1 overflow-clip">
          <div className="flex min-w-0 flex-1 flex-col overflow-x-clip pt-1">
            <Outlet />
          </div>
        </main>
      </SidebarProvider>
    </PageLayout>
  );
}
