import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Separator } from "@/components/ui/separator";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  type SidebarSection,
  useSidebar,
} from "@/components/ui/sidebar";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { cn } from "@/utils/utils";
import { useSearchContext } from "../index";
import { NAV_ITEMS } from "./sidebar-nav-items";

export type { SidebarSection };
export { NAV_ITEMS };

// The feature-view tabs (per-flow surfaces) sit below the separator. "agent" is
// the first of them, but it only shows for agent flows, so the separator is
// drawn before whichever one survives the flow_type filter — never a stray
// divider or a double one.
const FEATURE_SECTION_IDS = new Set<SidebarSection>([
  "agent",
  "memories",
  "traces",
]);

const SidebarSegmentedNav = () => {
  const { t } = useTranslation();
  const { activeSection, setActiveSection, toggleSidebar, open } = useSidebar();
  const { setSearch } = useSearchContext();
  const setPlaygroundOpen = usePlaygroundStore((state) => state.setIsOpen);
  const setPlaygroundFullscreen = usePlaygroundStore(
    (state) => state.setIsFullscreen,
  );
  // The Agent tab is only meaningful for flows classified as agents. Gate it
  // here at the render site (not in the shared NAV_ITEMS, which the welcome
  // faux-rail maps unconditionally and whose test can't take store imports).
  const isAgent = useFlowsManagerStore(
    (state) => state.currentFlow?.flow_type === "agent",
  );

  const items = NAV_ITEMS.filter((item) => item.id !== "agent" || isAgent);
  const firstFeatureIndex = items.findIndex((item) =>
    FEATURE_SECTION_IDS.has(item.id),
  );

  return (
    <div className="flex h-full flex-col border-r border-border bg-background">
      <SidebarMenu className="gap-2 py-1">
        {items.map((item, index) => (
          <div key={item.id}>
            {index === firstFeatureIndex && (
              <Separator className="mx-auto my-1 w-5" />
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
                >
                  <ForwardedIconComponent
                    name={item.icon}
                    className="h-5 w-5"
                  />
                  <span className="sr-only">{t(item.label)}</span>
                </SidebarMenuButton>
              </ShadTooltip>
            </SidebarMenuItem>
          </div>
        ))}
      </SidebarMenu>
    </div>
  );
};

export default SidebarSegmentedNav;
