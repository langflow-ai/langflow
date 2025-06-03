import ShadTooltip from "@/components/common/shadTooltipComponent";
import useFlowStore from "@/stores/flowStore";
import { checkChatInput, checkWebhookInput } from "@/utils/reactflowUtils";
import { removeCountFromString } from "@/utils/utils";
import { useMemo } from "react";
import { disableItem } from "../../helpers/disable-item";
import { getDisabledTooltip } from "../../helpers/get-disabled-tooltip";
import { UniqueInputsComponents } from "../../types";
import SidebarDraggableComponent from "../sidebarDraggableComponent";

const SidebarItemsList = ({
  item,
  dataFilter,
  nodeColors,
  onDragStart,
  sensitiveSort,
}) => {
  return (
    <div className="flex flex-col gap-1 py-2">
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
        .map((SBItemName, idx) => {
          const currentItem = dataFilter[item.name][SBItemName];

          if (SBItemName === "ChatInput" || SBItemName === "Webhook") {
            return (
              <UniqueInputsDraggableComponent
                item={item}
                currentItem={currentItem}
                SBItemName={SBItemName}
                idx={idx}
                onDragStart={onDragStart}
                nodeColors={nodeColors}
              />
            );
          }
          return (
            <ShadTooltip
              content={currentItem.display_name}
              side="right"
              key={idx}
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
                official={currentItem.official === false ? false : true}
                beta={currentItem.beta ?? false}
                legacy={currentItem.legacy ?? false}
                disabled={false}
                disabledTooltip={""}
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
  idx,
  onDragStart,
  nodeColors,
}) => {
  const nodes = useFlowStore((state) => state.nodes);
  const chatInputAdded = useMemo(() => checkChatInput(nodes), [nodes]);
  const webhookInputAdded = useMemo(() => checkWebhookInput(nodes), [nodes]);
  const uniqueInputsComponents: UniqueInputsComponents = useMemo(() => {
    return {
      chatInput: chatInputAdded,
      webhookInput: webhookInputAdded,
    };
  }, [chatInputAdded, webhookInputAdded]);

  return (
    <ShadTooltip content={currentItem.display_name} side="right" key={idx}>
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
        official={currentItem.official === false ? false : true}
        beta={currentItem.beta ?? false}
        legacy={currentItem.legacy ?? false}
        disabled={disableItem(SBItemName, uniqueInputsComponents)}
        disabledTooltip={getDisabledTooltip(SBItemName, uniqueInputsComponents)}
      />
    </ShadTooltip>
  );
};
