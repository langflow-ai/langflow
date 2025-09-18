import { memo } from "react";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
} from "@/components/ui/sidebar";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import { SIDEBAR_BUNDLES } from "@/utils/styleUtils";
import type { CategoryGroupProps } from "../types";
import { CategoryDisclosure } from "./categoryDisclouse";
import { SearchConfigTrigger } from "./searchConfigTrigger";

export const CategoryGroup = memo(function CategoryGroup({
  dataFilter,
  sortedCategories,
  CATEGORIES,
  openCategories,
  setOpenCategories,
  search,
  nodeColors,
  onDragStart,
  sensitiveSort,
  showConfig,
  setShowConfig,
}: CategoryGroupProps) {
  return (
    <SidebarGroup className="p-3">
      {ENABLE_NEW_SIDEBAR && (
        <SidebarGroupLabel className="cursor-default flex items-center justify-between w-full">
          <span>Components</span>
          <SearchConfigTrigger
            showConfig={showConfig}
            setShowConfig={setShowConfig}
          />
        </SidebarGroupLabel>
      )}
      <SidebarGroupContent>
        <SidebarMenu>
          {Object.entries(dataFilter)
            .filter(
              ([categoryName, items]) =>
                // filter out bundles and MCP
                !SIDEBAR_BUNDLES.some((cat) => cat.name === categoryName) &&
                categoryName !== "custom_component" &&
                categoryName !== "MCP" &&
                Object.keys(items).length > 0,
            )
            .sort(([aName], [bName]) => {
              const categoryList =
                search !== ""
                  ? sortedCategories
                  : CATEGORIES.map((c) => c.name);
              const aIndex = categoryList.indexOf(aName);
              const bIndex = categoryList.indexOf(bName);

              // If neither is in CATEGORIES, keep their relative order
              if (aIndex === -1 && bIndex === -1) return 0;
              // If only a is not in CATEGORIES, put it after b
              if (aIndex === -1) return 1;
              // If only b is not in CATEGORIES, put it after a
              if (bIndex === -1) return -1;
              // If both are in CATEGORIES, sort by their index
              return aIndex - bIndex;
            })
            .map(([categoryName]) => {
              const item = CATEGORIES.find(
                (cat) => cat.name === categoryName,
              ) ?? {
                name: categoryName,
                icon: "folder",
                display_name: categoryName,
              };
              return (
                <CategoryDisclosure
                  key={categoryName}
                  item={item}
                  openCategories={openCategories}
                  setOpenCategories={setOpenCategories}
                  dataFilter={dataFilter}
                  nodeColors={nodeColors}
                  onDragStart={onDragStart}
                  sensitiveSort={sensitiveSort}
                />
              );
            })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
});

CategoryGroup.displayName = "CategoryGroup";
