import { useEffect, useState } from "react";
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
  {
    id: "add_note",
    icon: "sticky-note",
    label: "Sticky Notes",
    tooltip: "Add Sticky Notes",
  },
];

const SidebarSegmentedNav = () => {
  const { activeSection, setActiveSection, toggleSidebar, open } = useSidebar();
  const { focusSearch, setSearch } = useSearchContext();
  const [isAddNoteActive, setIsAddNoteActive] = useState(false);
  const handleAddNote = () => {
    window.dispatchEvent(new Event("lf:start-add-note"));
    setIsAddNoteActive(true);
  };

  useEffect(() => {
    const onEnd = () => setIsAddNoteActive(false);
    window.addEventListener("lf:end-add-note", onEnd);
    return () => window.removeEventListener("lf:end-add-note", onEnd);
  }, []);

  return (
    <div className="flex h-full flex-col border-r border-border bg-background">
      <SidebarMenu className="gap-2 py-1">
        {NAV_ITEMS.map((item) => (
          <div key={item.id}>
            {item.id === "add_note" && <Separator className="w-full" />}
            <SidebarMenuItem className="px-1">
              <ShadTooltip content={item.tooltip} side="right">
                <SidebarMenuButton
                  size="md"
                  onClick={(e) => {
                    if (item.id === "add_note") {
                      e.stopPropagation();
                      handleAddNote();
                      return;
                    }

                    setSearch?.("");
                    if (activeSection === item.id && open) {
                      toggleSidebar();
                    } else {
                      setActiveSection(item.id);
                      if (!open) {
                        toggleSidebar();
                      }
                      if (item.id === "search") {
                        setTimeout(() => focusSearch(), 100);
                      }
                    }
                  }}
                  isActive={
                    item.id === "add_note"
                      ? isAddNoteActive
                      : activeSection === item.id
                  }
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-md p-0 transition-all duration-200",
                    (
                      item.id === "add_note"
                        ? isAddNoteActive
                        : activeSection === item.id
                    )
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
