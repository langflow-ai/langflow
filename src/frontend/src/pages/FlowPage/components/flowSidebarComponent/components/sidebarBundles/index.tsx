import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
} from "@/components/ui/sidebar";
import { memo, useCallback, useMemo, useState } from "react";
import { SidebarGroupProps } from "../../types";
import { BundleItem } from "../bundleItems";

export const MemoizedSidebarGroup = memo(
  ({
    BUNDLES,
    search,
    sortedCategories,
    dataFilter,
    nodeColors,
    onDragStart,
    sensitiveSort,
    handleKeyDownInput,
    openCategories,
    setOpenCategories,
  }: SidebarGroupProps) => {
    const sortedBundles = useMemo(() => {
      return BUNDLES.toSorted((a, b) => {
        const referenceArray = search !== "" ? sortedCategories : BUNDLES;
        return (
          referenceArray.findIndex((value) => value === a.name) -
          referenceArray.findIndex((value) => value === b.name)
        );
      });
    }, [BUNDLES, search, sortedCategories]);

    return (
      <SidebarGroup className="p-3">
        <SidebarGroupLabel className="cursor-default">Bundles</SidebarGroupLabel>
        <SidebarGroupContent>
          <SidebarMenu>
            {sortedBundles.map((item) => (
              <BundleItem
                key={item.name}
                item={item}
                openCategories={openCategories}
                setOpenCategories={setOpenCategories}
                dataFilter={dataFilter}
                nodeColors={nodeColors}
                onDragStart={onDragStart}
                sensitiveSort={sensitiveSort}
                handleKeyDownInput={handleKeyDownInput}
              />
            ))}
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>
    );
  },
);

MemoizedSidebarGroup.displayName = "MemoizedSidebarGroup";

export default MemoizedSidebarGroup;
