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

// The feature-view tabs (per-flow surfaces) sit below the separator. "agent" is
// the first of them; the separator is drawn before it so there's never a stray
// divider or a double one.
const FEATURE_SECTION_IDS = new Set<SidebarSection>([
  "agent",
  "memories",
  "traces",
]);

type SidebarSegmentedNavProps = {
  hiddenFromTabOrder?: boolean;
};

const SidebarSegmentedNav = ({
  hiddenFromTabOrder = false,
}: SidebarSegmentedNavProps) => {
  const { t } = useTranslation();
  const { activeSection, setActiveSection, toggleSidebar, open } = useSidebar();
  const { setSearch } = useSearchContext();
  const setPlaygroundOpen = usePlaygroundStore((state) => state.setIsOpen);
  const setPlaygroundFullscreen = usePlaygroundStore(
    (state) => state.setIsFullscreen,
  );
  // The Agent tab is always available; it handles eligibility inside the tab.
  const items = NAV_ITEMS;
  const firstFeatureIndex = items.findIndex((item) =>
    FEATURE_SECTION_IDS.has(item.id),
  );

  return (
    <div
      className="flex h-full flex-col border-r border-border bg-background"
      aria-hidden={hiddenFromTabOrder || undefined}
    >
      <SidebarMenu className="gap-2 py-1">
        {items.map((item, index) => (
          <Fragment key={item.id}>
            {index === firstFeatureIndex && (
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
                      if (FEATURE_SECTION_IDS.has(item.id)) {
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
                  data-sidebar-nav-item={item.id}
                  tabIndex={hiddenFromTabOrder ? -1 : undefined}
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
