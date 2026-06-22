import { Fragment } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  type SidebarSection,
  useSidebar,
} from "@/components/ui/sidebar";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { cn } from "@/utils/utils";
import { useSearchContext } from "../index";
import { NAV_ITEMS } from "./sidebar-nav-items";

export type { SidebarSection };
export { NAV_ITEMS };

const SidebarSegmentedNav = () => {
  const { t } = useTranslation();
  const { activeSection, setActiveSection, toggleSidebar, open } = useSidebar();
  const { setSearch } = useSearchContext();
  const setPlaygroundOpen = usePlaygroundStore((state) => state.setIsOpen);
  const setPlaygroundFullscreen = usePlaygroundStore(
    (state) => state.setIsFullscreen,
  );

  return (
    <div className="flex h-full flex-col border-r border-border bg-background">
      <SidebarMenu className="gap-2 py-1">
        {NAV_ITEMS.map((item) => (
          <Fragment key={item.id}>
            {item.id === "memories" && (
              <li
                role="separator"
                aria-hidden="true"
                className="mx-auto my-1 w-5 border-t border-border"
              />
            )}
            <SidebarMenuItem className="px-1 pt-1">
              <ShadTooltip content={t(item.tooltip)} side="right">
                <SidebarMenuButton
                  size="md"
                  onClick={() => {
                    if (item.id === "traces") {
                      setPlaygroundOpen(false);
                      setPlaygroundFullscreen(false);
                    }

                    setSearch?.("");
                    if (activeSection === item.id && open) {
                      if (item.id === "traces" || item.id === "memories") {
                        setActiveSection("components");
                      } else {
                        toggleSidebar();
                      }
                    } else {
                      setActiveSection(item.id);
                      if (!open) {
                        toggleSidebar();
                      }
                    }
                  }}
                  isActive={activeSection === item.id}
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-md p-0 transition-all duration-200",
                    activeSection === item.id
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  )}
                  data-testid={`sidebar-nav-${item.id}`}
                >
                  <ForwardedIconComponent
                    name={item.icon}
                    className="h-5 w-5"
                  />
                  <span className="sr-only">{t(item.label)}</span>
                </SidebarMenuButton>
              </ShadTooltip>
            </SidebarMenuItem>
          </Fragment>
        ))}
      </SidebarMenu>
    </div>
  );
};

export default SidebarSegmentedNav;
