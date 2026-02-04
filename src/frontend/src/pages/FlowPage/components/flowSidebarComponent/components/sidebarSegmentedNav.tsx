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
  {
    id: "logs",
    icon: "ScrollText",
    label: "Logs",
    tooltip: "Logs",
  },
  {
    id: "messages",
    icon: "MessagesSquare",
    label: "Messages",
    tooltip: "Messages",
  },
  {
    id: "evaluations",
    icon: "FlaskConical",
    label: "Evaluations",
    tooltip: "Evaluations",
  },
];

const SidebarSegmentedNav = () => {
  const { activeSection, setActiveSection, toggleSidebar, open } = useSidebar();
  const { focusSearch, setSearch } = useSearchContext();

  return (
    <div className="flex h-full flex-col border-r border-border bg-background">
      <SidebarMenu className="gap-2 py-1">
        {NAV_ITEMS.map((item) => (
          <div key={item.id}>
            {item.id === "logs" && <Separator className="w-full" />}
            <SidebarMenuItem className="px-1">
              <ShadTooltip content={item.tooltip} side="right">
                <SidebarMenuButton
                  size="md"
                  onClick={() => {
                    setSearch?.("");
                    if (activeSection === item.id && open) {
                      // For logs and messages, don't toggle sidebar - they control main content
                      if (item.id !== "logs" && item.id !== "messages") {
                        toggleSidebar();
                      }
                    } else {
                      setActiveSection(item.id);
                      if (!open) {
                        toggleSidebar();
                      }
                      // Auto-focus search when opening components, mcp, or bundles
                      if (["components", "mcp", "bundles"].includes(item.id)) {
                        setTimeout(() => focusSearch(), 100);
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
                  <span className="sr-only">{item.label}</span>
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
