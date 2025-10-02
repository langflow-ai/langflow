import { memo, useMemo } from "react";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
} from "@/components/ui/sidebar";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import type { SidebarGroupProps } from "../types";
import { BundleItem } from "./bundleItems";
import { SearchConfigTrigger } from "./searchConfigTrigger";

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
    showSearchConfigTrigger,
    showConfig,
    setShowConfig,
  }: SidebarGroupProps) => {
    const sortedBundles = useMemo(() => {
      return BUNDLES.toSorted((a, b) => {
        const referenceArray = search !== "" ? sortedCategories : BUNDLES;
        return (
          referenceArray.findIndex((value) => value === a.name) -
          referenceArray.findIndex((value) => value === b.name)
        );
      }).filter(
        (item: { name: string | number }) =>
          dataFilter[item.name] &&
          Object.keys(dataFilter[item.name]).length > 0,
      );
    }, [BUNDLES, search, sortedCategories, dataFilter]);

    return (
      <SidebarGroup className="p-3 pr-2">
        <SidebarGroupLabel className="cursor-default w-full flex items-center justify-between">
          <span>Bundles</span>
          {showSearchConfigTrigger && ENABLE_NEW_SIDEBAR && (
            <SearchConfigTrigger
              showConfig={showConfig}
              setShowConfig={setShowConfig}
            />
          )}
        </SidebarGroupLabel>
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
