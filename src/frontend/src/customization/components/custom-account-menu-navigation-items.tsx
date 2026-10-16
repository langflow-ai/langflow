import { useTranslation } from "react-i18next";
import { HeaderMenuItemButton } from "@/components/core/appHeaderComponent/components/HeaderMenu";
import { CustomAdminPageMenuItem } from "@/customization/components/custom-admin-page-menu-item";

export interface CustomAccountMenuNavigationItemsProps {
  onNavigate: (path: string) => void;
}

/**
 * Navigation entries shown in the account menu.
 *
 * Enterprise replaces this seam when these destinations are available from
 * its persistent application navigation.
 */
export function CustomAccountMenuNavigationItems({
  onNavigate,
}: CustomAccountMenuNavigationItemsProps) {
  const { t } = useTranslation();

  return (
    <>
      <HeaderMenuItemButton onClick={() => onNavigate("/settings")}>
        <span data-testid="menu_settings_button" id="menu_settings_button">
          {t("account.settings")}
        </span>
      </HeaderMenuItemButton>
      <CustomAdminPageMenuItem onNavigate={onNavigate} />
    </>
  );
}

export default CustomAccountMenuNavigationItems;
