import { useMemo } from "react";
import { isBlockedByCatalogPolicy } from "@/CustomNodes/helpers/check-code-validity";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import useFlowStore from "@/stores/flowStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { getPresentComponentTypes } from "@/utils/componentConstraints";
import { removeCountFromString } from "@/utils/utils";
import { TOOLTIP_MESSAGES } from "../helpers/constants";
import { disableItem } from "../helpers/disable-item";
import { getDisabledTooltip } from "../helpers/get-disabled-tooltip";
import SidebarDraggableComponent from "./sidebarDraggableComponent";

const SidebarItemsList = ({
  item,
  dataFilter,
  nodeColors,
  onDragStart,
  sensitiveSort,
}) => {
  // An administrator's catalog policy refuses these server side, so offering
  // the affordance only lets a user build a flow that cannot save or run. The
  // same set gates the node banner, so the palette and the canvas agree.
  const blockedComponentTypes = useUtilityStore(
    (state) => state.blockedComponentTypes,
  );

  return (
    <div className="flex flex-col gap-1 py-1">
      {Object.keys(dataFilter[item.name])
        .sort((a, b) => {
          const itemA = dataFilter[item.name][a];
          const itemB = dataFilter[item.name][b];

          // Sort by priority if available
          if (itemA.priority !== undefined || itemB.priority !== undefined) {
            const priorityA = itemA.priority ?? Number.MAX_SAFE_INTEGER;
            const priorityB = itemB.priority ?? Number.MAX_SAFE_INTEGER;
            if (priorityA !== priorityB) {
              return priorityA - priorityB;
            }
          }

          // Otherwise use the existing sorting logic
          return itemA.score && itemB.score
            ? itemA.score - itemB.score
            : sensitiveSort(itemA.display_name, itemB.display_name);
        })
        .map((SBItemName) => {
          const currentItem = dataFilter[item.name][SBItemName];
          if (SBItemName === "MCPTools") {
            return null;
          }

          if (SBItemName === "ChatInput" || SBItemName === "Webhook") {
            return (
              <UniqueInputsDraggableComponent
                key={SBItemName}
                item={item}
                currentItem={currentItem}
                SBItemName={SBItemName}
                onDragStart={onDragStart}
                nodeColors={nodeColors}
                blockedComponentTypes={blockedComponentTypes}
              />
            );
          }

          const isBlocked = isBlockedByCatalogPolicy(
            blockedComponentTypes,
            removeCountFromString(SBItemName),
          );
          return (
            <ShadTooltip
              content={currentItem.display_name}
              side="right"
              key={SBItemName}
            >
              <SidebarDraggableComponent
                sectionName={item.name}
                apiClass={currentItem}
                icon={currentItem.icon ?? item.icon ?? "Unknown"}
                onDragStart={(event) =>
                  onDragStart(event, {
                    type: removeCountFromString(SBItemName),
                    node: currentItem,
                  })
                }
                color={nodeColors[item.name]}
                itemName={SBItemName}
                error={!!currentItem.error}
                display_name={currentItem.display_name}
                official={currentItem.official !== false}
                beta={currentItem.beta ?? false}
                legacy={currentItem.legacy ?? false}
                disabled={isBlocked}
                disabledTooltip={
                  isBlocked ? TOOLTIP_MESSAGES.BLOCKED_BY_CATALOG_POLICY : ""
                }
              />
            </ShadTooltip>
          );
        })}
    </div>
  );
};

export default SidebarItemsList;

const UniqueInputsDraggableComponent = ({
  item,
  currentItem,
  SBItemName,
  onDragStart,
  nodeColors,
  blockedComponentTypes,
}) => {
  const nodes = useFlowStore((state) => state.nodes);
  const presentComponentTypes = useMemo(
    () => getPresentComponentTypes(nodes),
    [nodes],
  );
  // A catalog block outranks a placement constraint: the placement reason
  // ("already added") would tell the user to remove a node and try again, which
  // can never work for a component the policy refuses outright.
  const isBlocked = isBlockedByCatalogPolicy(
    blockedComponentTypes,
    removeCountFromString(SBItemName),
  );

  return (
    <ShadTooltip
      content={currentItem.display_name}
      side="right"
      key={SBItemName}
    >
      <SidebarDraggableComponent
        sectionName={item.name}
        apiClass={currentItem}
        icon={currentItem.icon ?? item.icon ?? "Unknown"}
        onDragStart={(event) =>
          onDragStart(event, {
            type: removeCountFromString(SBItemName),
            node: currentItem,
          })
        }
        color={nodeColors[item.name]}
        itemName={SBItemName}
        error={!!currentItem.error}
        display_name={currentItem.display_name}
        official={currentItem.official !== false}
        beta={currentItem.beta ?? false}
        legacy={currentItem.legacy ?? false}
        disabled={isBlocked || disableItem(SBItemName, presentComponentTypes)}
        disabledTooltip={
          isBlocked
            ? TOOLTIP_MESSAGES.BLOCKED_BY_CATALOG_POLICY
            : getDisabledTooltip(SBItemName, presentComponentTypes)
        }
      />
    </ShadTooltip>
  );
};
