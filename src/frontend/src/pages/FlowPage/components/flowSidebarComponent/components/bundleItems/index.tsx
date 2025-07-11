import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  Disclosure,
  DisclosureContent,
  DisclosureTrigger,
} from "@/components/ui/disclosure";
import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import { memo, useCallback } from "react";
import { BundleItemProps } from "../../types";
import SidebarItemsList from "../sidebarItemsList";

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
    if (
      !dataFilter[item.name] ||
      Object.keys(dataFilter[item.name]).length === 0
    ) {
      return null;
    }

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
