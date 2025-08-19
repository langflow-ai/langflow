import { memo, useCallback } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  Disclosure,
  DisclosureContent,
  DisclosureTrigger,
} from "@/components/ui/disclosure";
import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import type { BundleItemProps } from "../types";
import SidebarItemsList from "./sidebarItemsList";

export const BundleItem = memo(
  ({
    item,
    openCategories,
    setOpenCategories,
    dataFilter,
    nodeColors,
    onDragStart,
    sensitiveSort,
    handleKeyDownInput,
  }: BundleItemProps) => {
    const isOpen = openCategories.includes(item.name);

    const handleOpenChange = useCallback(
      (isOpen: boolean) => {
        setOpenCategories((prev: string[]) =>
          isOpen
            ? [...prev, item.name]
            : prev.filter((cat) => cat !== item.name),
        );
      },
      [item.name, setOpenCategories],
    );

    return (
      <Disclosure key={item.name} open={isOpen} onOpenChange={handleOpenChange}>
        <SidebarMenuItem>
          <DisclosureTrigger className="group/collapsible">
            <SidebarMenuButton asChild>
              <div
                role="button"
                tabIndex={0}
                onKeyDown={(e) => handleKeyDownInput(e, item.name)}
                className="user-select-none flex cursor-pointer items-center gap-2"
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
              onDragStart={onDragStart}
              sensitiveSort={sensitiveSort}
            />
          </DisclosureContent>
        </SidebarMenuItem>
      </Disclosure>
    );
  },
);

BundleItem.displayName = "BundleItem";
