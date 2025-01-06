import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
} from "@/components/ui/sidebar";
import { memo } from "react";
import { CategoryGroupProps } from "../../types";
import { CategoryDisclosure } from "../categoryDisclouse";

export const CategoryGroup = memo(function CategoryGroup({
  dataFilter,
  sortedCategories,
  CATEGORIES,
  openCategories,
  setOpenCategories,
  search,
  nodeColors,
  chatInputAdded,
  onDragStart,
  sensitiveSort,
}: CategoryGroupProps) {
  return (
    <SidebarGroup className="p-3">
      <SidebarGroupContent>
        <SidebarMenu>
          {CATEGORIES.toSorted(
            (a, b) =>
              (search !== "" ? sortedCategories : CATEGORIES).findIndex(
                (value) => value === a.name,
              ) -
              (search !== "" ? sortedCategories : CATEGORIES).findIndex(
                (value) => value === b.name,
              ),
          ).map(
            (item) =>
              dataFilter[item.name] &&
              Object.keys(dataFilter[item.name]).length > 0 && (
                <CategoryDisclosure
                  key={item.name}
                  item={item}
                  openCategories={openCategories}
                  setOpenCategories={setOpenCategories}
                  dataFilter={dataFilter}
                  nodeColors={nodeColors}
                  chatInputAdded={chatInputAdded}
                  onDragStart={onDragStart}
                  sensitiveSort={sensitiveSort}
                />
              ),
          )}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
});

CategoryGroup.displayName = "CategoryGroup";
