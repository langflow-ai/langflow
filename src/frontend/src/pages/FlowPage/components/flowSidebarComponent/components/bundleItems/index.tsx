import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  Disclosure,
  DisclosureContent,
  DisclosureTrigger,
} from "@/components/ui/disclosure";
import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import { memo } from "react";
import { BundleItemProps } from "../../types";
import SidebarItemsList from "../sidebarItemsList";

export const BundleItem = memo(
  ({
    item,
    isOpen,
    onOpenChange,
    dataFilter,
    nodeColors,
    uniqueInputsComponents,
    onDragStart,
    sensitiveSort,
    handleKeyDownInput,
  }: BundleItemProps) => {
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
                    className="text-muted-foreground group-aria-expanded/collapsible:text-primary h-4 w-4"
                  />
                  <span className="flex-1 group-aria-expanded/collapsible:font-semibold">
                    {item.display_name}
                  </span>
                  <ForwardedIconComponent
                    name="ChevronRight"
                    className="text-muted-foreground -mr-1 h-4 w-4 transition-all group-aria-expanded/collapsible:rotate-90"
                  />
                </div>
              </SidebarMenuButton>
            </DisclosureTrigger>
            <DisclosureContent>
              <SidebarItemsList
                item={item}
                dataFilter={dataFilter}
                nodeColors={nodeColors}
                uniqueInputsComponents={uniqueInputsComponents}
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
