import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
} from "@/components/ui/sidebar";
import { memo, useMemo } from "react";
import { BundleItem } from "../bundleItems";

export const MemoizedSidebarGroup = memo(
  ({
    BUNDLES,
    search,
    sortedCategories,
    dataFilter,
    nodeColors,
    chatInputAdded,
    onDragStart,
    sensitiveSort,
    openCategories,
    setOpenCategories,
    handleKeyDownInput,
  }: {
    BUNDLES: any;
    search: any;
    sortedCategories: any;
    dataFilter: any;
    nodeColors: any;
    chatInputAdded: any;
    onDragStart: any;
    sensitiveSort: any;
    openCategories: any;
    setOpenCategories: any;
    handleKeyDownInput: any;
  }) => {
    // Memoize the sorted bundles calculation
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
        <SidebarGroupLabel>Bundles</SidebarGroupLabel>
        <SidebarGroupContent>
          <SidebarMenu>
            {sortedBundles.map((item) => (
              <BundleItem
                key={item.name}
                item={item}
                isOpen={openCategories.includes(item.name)}
                onOpenChange={(isOpen) => {
                  setOpenCategories((prev) =>
                    isOpen
                      ? [...prev, item.name]
                      : prev.filter((cat) => cat !== item.name),
                  );
                }}
                dataFilter={dataFilter}
                nodeColors={nodeColors}
                chatInputAdded={chatInputAdded}
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
