import { useTranslation } from "react-i18next";
import { Outlet, useLocation } from "react-router-dom";
import CustomSettingsPageFrame from "@/customization/components/custom-settings-page-frame";
import { useDocumentTitle } from "@/hooks/use-document-title";
import { useSettingsSidebarItems } from "./use-settings-sidebar-items";

export default function SettingsPage(): JSX.Element {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const sidebarNavItems = useSettingsSidebarItems();

  // Every settings section shares this shell, so the tab title has to name the
  // open section rather than just "Settings" (WCAG 2.4.2).
  const activeNavItem = sidebarNavItems.find(
    (item) => item.href && pathname.startsWith(item.href),
  );
  useDocumentTitle(activeNavItem?.title ?? t("settings.title"));

  return (
    <CustomSettingsPageFrame
      title={t("settings.title")}
      description={t("settings.description")}
      items={sidebarNavItems}
    >
      <Outlet />
    </CustomSettingsPageFrame>
  );
}
