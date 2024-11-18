import ShadTooltip from "@/components/common/shadTooltipComponent";
import { nodeColors, nodeIconsLucide, nodeNames } from "@/utils/styleUtils";
import { removeCountFromString } from "@/utils/utils";
import DisclosureComponent from "../../DisclosureComponent";
import SidebarDraggableComponent from "../sideBarDraggableComponent";
import sensitiveSort from "../utils/sensitive-sort";

export function SidebarCategoryComponent({
  search,
  getFilterEdge,
  category,
  name,
  onDragStart,
}) {
  return (
    <DisclosureComponent
      isChild={false}
      defaultOpen={
        getFilterEdge.length !== 0 || search.length !== 0 ? true : false
      }
      button={{
        title: nodeNames[name] ?? nodeNames.unknown,
        Icon: nodeIconsLucide[name] ?? nodeIconsLucide.unknown,
      }}
    >
      <div className="side-bar-components-gap">
        {Object.keys(category)
          .sort((a, b) =>
            sensitiveSort(category[a].display_name, category[b].display_name),
          )
          .map((SBItemName: string, idx) => (
            <ShadTooltip
              content={category[SBItemName].display_name}
              side="right"
              key={idx}
            >
              <SidebarDraggableComponent
                sectionName={name as string}
                apiClass={category[SBItemName]}
                key={idx}
                onDragStart={(event) =>
                  onDragStart(event, {
                    //split type to remove type in nodes saved with same name removing it's
                    type: removeCountFromString(SBItemName),
                    node: category[SBItemName],
                  })
                }
                color={nodeColors[name]}
                itemName={SBItemName}
                //convert error to boolean
                error={!!category[SBItemName].error}
                display_name={category[SBItemName].display_name}
                official={
                  category[SBItemName].official === false ? false : true
                }
              />
            </ShadTooltip>
          ))}
      </div>
    </DisclosureComponent>
  );
}
