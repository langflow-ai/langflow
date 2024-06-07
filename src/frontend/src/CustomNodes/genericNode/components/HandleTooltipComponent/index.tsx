import { useRef } from "react";
import { TOOLTIP_EMPTY } from "../../../../constants/constants";
import { groupByFamily } from "../../../../utils/utils";
import TooltipRenderComponent from "../tooltipRenderComponent";
import { useTypesStore } from "../../../../stores/typesStore";
import { NodeType } from "../../../../types/flow";
import useFlowStore from "../../../../stores/flowStore";

export default function HandleTooltips({
  left,
  tooltipTitle,
}: {
  left: boolean;
  nodes: NodeType[];
  tooltipTitle: string;
}) {
  const myData = useTypesStore((state) => state.data);
  const nodes = useFlowStore((state) => state.nodes);

  let groupedObj: any = groupByFamily(myData, tooltipTitle!, left, nodes!);

  if (groupedObj && groupedObj.length > 0) {
    //@ts-ignore
    return groupedObj.map((item, index) => {
      return <TooltipRenderComponent index={index} item={item} left={left} />;
    });
  } else {
    //@ts-ignore
    return <span data-testid={`empty-tooltip-filter`}>{TOOLTIP_EMPTY}</span>;
  }
}
