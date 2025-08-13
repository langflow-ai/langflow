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

export type { SidebarSection };

interface NavItem {
  id: SidebarSection;
  icon: string;
  label: string;
  tooltip: string;
}

const NAV_ITEMS: NavItem[] = [
  {
    id: "agents",
    icon: "bot",
    label: "Agents",
    tooltip: "Agents",
  },
  {
    id: "components",
    icon: "component",
    label: "Components",
    tooltip: "Components",
  },
  {
    id: "bundles",
    icon: "blocks",
    label: "Bundles",
    tooltip: "Bundles",
  },
  {
    id: "mcp",
    icon: "Mcp",
    label: "MCP",
    tooltip: "MCP",
  },
];

export default function SidebarSegmentedNav() {
  const { activeSection, setActiveSection, toggleSidebar, open } = useSidebar();
  return (
    <div className="flex h-full flex-col border-r border-border bg-background">
      <SidebarMenu className="gap-2 p-1">
        {NAV_ITEMS.map((item) => (
          <SidebarMenuItem key={item.id}>
            <ShadTooltip content={item.tooltip} side="right">
              <SidebarMenuButton
                size="md"
                onClick={() => {
                  setActiveSection(item.id);
                  if (!open) {
                    toggleSidebar();
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
