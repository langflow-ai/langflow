import { memo, useCallback, useMemo } from "react";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
} from "@/components/ui/sidebar";
import { useTypesStore } from "@/stores/typesStore";
import { nodeColors } from "@/utils/styleUtils";
import { removeCountFromString } from "@/utils/utils";
import type { APIClassType } from "@/types/api";
import SidebarDraggableComponent from "./sidebarDraggableComponent";

const SavedComponentsSidebarGroup = memo(function SavedComponentsSidebarGroup({
  onDragStart,
}: {
  onDragStart: (
    event: React.DragEvent<any>,
    data: { type: string; node?: APIClassType },
  ) => void;
}) {
  const savedComponents = useTypesStore(
    (state) => state.data?.saved_components,
  );

  const sortedComponentNames = useMemo(() => {
    if (!savedComponents) return [];
    return Object.keys(savedComponents).sort((a, b) => {
      const displayA = savedComponents[a]?.display_name ?? a;
      const displayB = savedComponents[b]?.display_name ?? b;
      return displayA.localeCompare(displayB);
    });
  }, [savedComponents]);

  const handleDragStart = useCallback(
    (event: React.DragEvent<any>, itemName: string, item: APIClassType) => {
      onDragStart(event, {
        type: removeCountFromString(itemName),
        node: item,
      });
    },
    [onDragStart],
  );

  const isEmpty = sortedComponentNames.length === 0;

  return (
    <SidebarGroup className="p-3 pr-2">
      <SidebarGroupLabel className="cursor-default flex items-center justify-between w-full">
        <span>Saved</span>
      </SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {isEmpty ? (
            <div className="px-2 py-4 text-center text-sm text-muted-foreground">
              No saved components yet. Save a component from the canvas to see
              it here.
            </div>
          ) : (
            <div className="flex flex-col gap-1">
              {sortedComponentNames.map((itemName) => {
                const currentItem = savedComponents![itemName];
                return (
                  <ShadTooltip
                    content={currentItem.display_name}
                    side="right"
                    key={itemName}
                  >
                    <SidebarDraggableComponent
                      sectionName="saved_components"
                      apiClass={currentItem}
                      icon={currentItem.icon ?? "GradientSave"}
                      onDragStart={(event) =>
                        handleDragStart(event, itemName, currentItem)
                      }
                      color={nodeColors["saved_components"]}
                      itemName={itemName}
                      error={!!currentItem.error}
                      display_name={currentItem.display_name}
                      official={currentItem.official !== false}
                      beta={currentItem.beta ?? false}
                      legacy={currentItem.legacy ?? false}
                      disabled={false}
                      disabledTooltip=""
                    />
                  </ShadTooltip>
                );
              })}
            </div>
          )}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
});

SavedComponentsSidebarGroup.displayName = "SavedComponentsSidebarGroup";

export default SavedComponentsSidebarGroup;
