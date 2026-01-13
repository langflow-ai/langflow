import { memo } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { useGetGenerateComponentConfig } from "@/controllers/API/queries/generate-component";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import useAlertStore from "@/stores/alertStore";
import { useGenerateComponentStore } from "@/stores/generateComponentStore";
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
  const toggleTerminal = useGenerateComponentStore((state) => state.toggleTerminal);
  const { data: generateComponentConfigData } = useGetGenerateComponentConfig();
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const isGenerateComponentConfigured = generateComponentConfigData?.configured ?? false;

  const handleGenerateComponentClick = () => {
    if (!isGenerateComponentConfigured) {
      setErrorData({
        title: "Generate component requires configuration",
        list: [
          "ANTHROPIC_API_KEY is required to use Generate component.",
          "Please add it to your environment variables or configure it in Settings > Global Variables.",
        ],
      });
      return;
    }
    toggleTerminal();
  };

  return (
    <SidebarGroup className="p-2">
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
          {/* Generate Component - First Item */}
          <SidebarMenuItem>
            <SidebarMenuButton asChild className="!overflow-visible">
              <div
                data-testid="sidebar-generate-component-button"
                role="button"
                tabIndex={0}
                onClick={handleGenerateComponentClick}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    handleGenerateComponentClick();
                  }
                }}
                className="user-select-none flex cursor-pointer items-center gap-2"
              >
                <ForwardedIconComponent
                  name="Sparkles"
                  className="h-4 w-4"
                />
                <span className="whitespace-nowrap pr-1">
                  Generate component
                </span>
                <Badge
                  className="ml-auto shrink-0 bg-accent-pink hover:bg-accent-pink text-white border-0 rounded-md px-1.5 py-0 text-[10px] font-medium"
                >
                  New
                </Badge>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
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
