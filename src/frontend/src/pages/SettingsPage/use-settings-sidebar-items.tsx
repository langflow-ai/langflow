import { useTranslation } from "react-i18next";
import { CustomStoreSidebar } from "@/customization/components/custom-store-sidebar";
import {
  ENABLE_DATASTAX_LANGFLOW,
  ENABLE_PROFILE_ICONS,
} from "@/customization/feature-flags";
import useAuthStore from "@/stores/authStore";
import { useStoreStore } from "@/stores/storeStore";
import { useUtilityStore } from "@/stores/utilityStore";
import ForwardedIconComponent from "../../components/common/genericIconComponent";

export interface SettingsSidebarItem {
  href?: string;
  title: string;
  icon: React.ReactNode;
}

export function useSettingsSidebarItems(): SettingsSidebarItem[] {
  const { t } = useTranslation();
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const isSuperuser = Boolean(
    useAuthStore((state) => state.userData)?.is_superuser,
  );
  const hasStore = useStoreStore((state) => state.hasStore);
  const migrationEnabled = useUtilityStore(
    (state) => state.featureFlags.instance_migration === true,
  );
  const items: SettingsSidebarItem[] = [];

  if (ENABLE_PROFILE_ICONS || hasStore || !autoLogin) {
    items.push({
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

  items.push(
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
    items.push({
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

  if (!ENABLE_DATASTAX_LANGFLOW) {
    items.splice(2, 0, ...CustomStoreSidebar(true));
  }

  return items;
}
