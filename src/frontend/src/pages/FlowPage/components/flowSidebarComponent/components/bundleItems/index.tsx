import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  Disclosure,
  DisclosureContent,
  DisclosureTrigger,
} from "@/components/ui/disclosure";
import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import { memo } from "react";
import SidebarItemsList from "../sidebarItemsList";

export const BundleItem = memo(
  ({
    item,
    isOpen,
    onOpenChange,
    dataFilter,
    nodeColors,
    chatInputAdded,
    onDragStart,
    sensitiveSort,
    handleKeyDownInput,
  }: {
    item: any;
    isOpen: boolean;
    onOpenChange: (isOpen: boolean) => void;
    dataFilter: any;
    nodeColors: any;
    chatInputAdded: any;
    onDragStart: any;
    sensitiveSort: any;
    handleKeyDownInput: any;
  }) => {
    if (
      !dataFilter[item.name] ||
      Object.keys(dataFilter[item.name]).length === 0
    ) {
      return null;
    }

    return (
      <>
        <Disclosure key={item.name} open={isOpen} onOpenChange={onOpenChange}>
          <SidebarMenuItem>
            <DisclosureTrigger className="group/collapsible">
              <SidebarMenuButton asChild>
                <div
                  tabIndex={0}
                  onKeyDown={(e) => handleKeyDownInput(e, item.name)}
                  className="flex cursor-pointer items-center gap-2"
                  data-testid={`disclosure-bundles-${item.display_name.toLowerCase()}`}
                >
                  <ForwardedIconComponent
                    name={item.icon}
                    className="h-4 w-4 text-muted-foreground group-aria-expanded/collapsible:text-primary"
                  />
                  <span className="flex-1 group-aria-expanded/collapsible:font-semibold">
                    {item.display_name}
                  </span>
                  <ForwardedIconComponent
                    name="ChevronRight"
                    className="-mr-1 h-4 w-4 text-muted-foreground transition-all group-aria-expanded/collapsible:rotate-90"
                  />
                </div>
              </SidebarMenuButton>
            </DisclosureTrigger>
            <DisclosureContent>
              <SidebarItemsList
                item={item}
                dataFilter={dataFilter}
                nodeColors={nodeColors}
                chatInputAdded={chatInputAdded}
                onDragStart={onDragStart}
                sensitiveSort={sensitiveSort}
              />
            </DisclosureContent>
          </SidebarMenuItem>
        </Disclosure>
      </>
    );
  },
);

BundleItem.displayName = "BundleItem";
