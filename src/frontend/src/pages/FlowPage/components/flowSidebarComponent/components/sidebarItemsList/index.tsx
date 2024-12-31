import ShadTooltip from "@/components/common/shadTooltipComponent";
import { removeCountFromString } from "@/utils/utils";
import SidebarDraggableComponent from "../sidebarDraggableComponent";

const SidebarItemsList = ({
  item,
  dataFilter,
  nodeColors,
  chatInputAdded,
  onDragStart,
  sensitiveSort,
}) => {
  return (
    <div className="flex flex-col gap-1 py-2">
      {Object.keys(dataFilter[item.name])
        .sort((a, b) => {
          const itemA = dataFilter[item.name][a];
          const itemB = dataFilter[item.name][b];
          return itemA.score && itemB.score
            ? itemA.score - itemB.score
            : sensitiveSort(itemA.display_name, itemB.display_name);
        })
        .map((SBItemName, idx) => {
          const currentItem = dataFilter[item.name][SBItemName];

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
                disabled={SBItemName === "ChatInput" && chatInputAdded}
                disabledTooltip="Chat input already added"
              />
            </ShadTooltip>
          );
        })}
    </div>
  );
};

export default SidebarItemsList;
