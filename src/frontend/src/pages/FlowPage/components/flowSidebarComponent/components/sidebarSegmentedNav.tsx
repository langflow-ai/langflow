import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  type SidebarSection,
  useSidebar,
} from "@/components/ui/sidebar";
import { cn } from "@/utils/utils";
import { useSearchContext } from "../index";

export type { SidebarSection };

interface NavItem {
  id: SidebarSection;
  icon: string;
  label: string;
  tooltip: string;
}

export const NAV_ITEMS: NavItem[] = [
  {
    id: "search",
    icon: "search",
    label: "Search",
    tooltip: "Search",
  },
  {
    id: "components",
    icon: "component",
    label: "Components",
    tooltip: "Components",
  },
  {
    id: "mcp",
    icon: "Mcp",
    label: "MCP",
    tooltip: "MCP",
  },
  {
    id: "bundles",
    icon: "blocks",
    label: "Bundles",
    tooltip: "Bundles",
  },
];

export default function SidebarSegmentedNav() {
  const { activeSection, setActiveSection, toggleSidebar, open } = useSidebar();
  const { focusSearch, isSearchFocused, setSearch } = useSearchContext();
  return (
    <div className="flex h-full flex-col border-r border-border bg-background">
      <SidebarMenu className="gap-2 p-1">
        {NAV_ITEMS.map((item) => (
          <SidebarMenuItem key={item.id}>
            <ShadTooltip content={item.tooltip} side="right">
              <SidebarMenuButton
                size="md"
                onClick={() => {
                  setSearch?.("");
                  if (activeSection === item.id && open) {
                    toggleSidebar();
                  } else {
                    setActiveSection(item.id);
                    if (!open) {
                      toggleSidebar();
                    }
                    // Focus search input when search section is selected
                    if (item.id === "search") {
                      // Add a small delay to ensure the sidebar is open and input is rendered
                      setTimeout(() => focusSearch(), 100);
                    }
                  }
                }}
                isActive={
                  activeSection === item.id ||
                  (item.id === "search" && isSearchFocused)
                }
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-md p-0 transition-all duration-200",
                  activeSection === item.id ||
                    (item.id === "search" && isSearchFocused)
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )}
                data-testid={`sidebar-nav-${item.id}`}
              >
                <ForwardedIconComponent name={item.icon} className="h-5 w-5" />
                <span className="sr-only">{item.label}</span>
              </SidebarMenuButton>
            </ShadTooltip>
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    </div>
  );
}
