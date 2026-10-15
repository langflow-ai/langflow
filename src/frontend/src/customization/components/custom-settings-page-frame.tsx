import type { ReactNode } from "react";
import type { To } from "react-router-dom";
import PageLayout from "@/components/common/pageLayout";
import SideBarButtonsComponent from "@/components/core/sidebarComponent";
import { SidebarProvider } from "@/components/ui/sidebar";
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
  return (
    <PageLayout backTo={-1 as To} title={title} description={description}>
      <SidebarProvider width="15rem" defaultOpen={false}>
        <SideBarButtonsComponent items={items} />
        {/* Overflow is clipped. Neither box scrolls, and a box that hides its overflow is what a sticky element inside a page sticks to. */}
        <main className="flex min-w-0 flex-1 overflow-clip">
          <div className="flex min-w-0 flex-1 flex-col overflow-x-clip pt-1">
            {children}
          </div>
        </main>
      </SidebarProvider>
    </PageLayout>
  );
}
