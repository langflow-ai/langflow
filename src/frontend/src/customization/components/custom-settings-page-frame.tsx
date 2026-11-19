import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { type To, useLocation } from "react-router-dom";
import PageLayout from "@/components/common/pageLayout";
import SideBarButtonsComponent from "@/components/core/sidebarComponent";
import { SidebarProvider } from "@/components/ui/sidebar";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import type { SettingsSidebarItem } from "@/pages/SettingsPage/use-settings-sidebar-items";

export interface CustomSettingsPageFrameProps {
  children: ReactNode;
  description: string;
  items: SettingsSidebarItem[];
  title: string;
}

export default function CustomSettingsPageFrame({
  children,
  description,
  items,
  title,
}: CustomSettingsPageFrameProps) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const navigate = useCustomNavigate();
  const selected = items.find(
    (item) => item.href && pathname.endsWith(item.href),
  );
  return (
    <PageLayout backTo={-1 as To} title={title} description={description}>
      <SidebarProvider
        width="15rem"
        defaultOpen={false}
        className="min-h-0 flex-col gap-3 sm:flex-row sm:gap-0"
      >
        <nav aria-label={t("settings.nav.label")} className="sm:hidden">
          <select
            aria-label={t("settings.nav.label")}
            value={selected?.href ?? ""}
            onChange={(event) =>
              navigate(event.target.value, { replace: true })
            }
            className="w-full rounded-md border border-control bg-background p-2 text-sm"
          >
            {!selected && (
              <option value="" disabled>
                {title}
              </option>
            )}
            {items.map(
              (item) =>
                item.href && (
                  <option key={item.href} value={item.href}>
                    {item.title}
                  </option>
                ),
            )}
          </select>
        </nav>
        <div className="hidden sm:contents">
          <SideBarButtonsComponent items={items} />
        </div>
        {/* Only the content scrolls, so the Settings header and the menu stay in view; a sticky element inside a page sticks to this box. */}
        {/* The box reaches over the page's right and bottom padding, so its scrollbar keeps the page's spacing from the cards. */}
        <main
          data-testid="settings-content-scroll"
          className="-mb-6 -mr-6 flex min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-clip pb-6 pr-6"
        >
          <div className="flex min-w-0 flex-1 flex-col overflow-x-clip pt-1">
            {children}
          </div>
        </main>
      </SidebarProvider>
    </PageLayout>
  );
}
