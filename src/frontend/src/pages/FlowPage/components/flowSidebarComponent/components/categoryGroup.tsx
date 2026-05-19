import { memo } from "react";
import { useTranslation } from "react-i18next";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
} from "@/components/ui/sidebar";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import { SIDEBAR_BUNDLES } from "@/utils/styleUtils";
import { toTitleCase } from "@/utils/utils";
import { deriveBundleExtensionId } from "../helpers/derive-bundle-extension-id";
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
  const { t } = useTranslation();
  return (
    <SidebarGroup className="p-3 pr-2">
      {ENABLE_NEW_SIDEBAR && (
        <SidebarGroupLabel className="cursor-default flex items-center justify-between w-full">
          <span>{t("sidebar.components")}</span>
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
              const curated = CATEGORIES.find(
                (cat) => cat.name === categoryName,
              );
              // Runtime-discovered bundles (and any uncategorised in-tree
              // group such as ``codeagents`` / ``files_ingestion``) fall
              // through to the fallback below.  Render the raw folder name
              // as a humanised label (snake_case -> "Snake Case") and pick
              // a generic ``Package`` icon when the category looks like an
              // installed/registered extension; otherwise stay with the
              // existing ``folder`` glyph so plain in-tree groups don't
              // pretend to be extensions.
              const isExtensionBundle =
                deriveBundleExtensionId(categoryName, dataFilter) !== undefined;
              const item = curated ?? {
                name: categoryName,
                icon: isExtensionBundle ? "Package" : "folder",
                display_name: toTitleCase(categoryName) || categoryName,
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
