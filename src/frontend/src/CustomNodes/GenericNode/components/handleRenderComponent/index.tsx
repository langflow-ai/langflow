import { Handle, Position } from "reactflow";
import ShadTooltip from "../../../../components/shadTooltipComponent";
import { Button } from "../../../../components/ui/button";
import {
  isValidConnection,
  scapedJSONStringfy,
} from "../../../../utils/reactflowUtils";
import { classNames, cn, groupByFamily } from "../../../../utils/utils";
import HandleTooltips from "../HandleTooltipComponent";
import { title } from "process";

export default function HandleRenderComponent({
  left,
  nodes,
  tooltipTitle,
  proxy,
  id,
  title,
  edges,
  myData,
  colors,
  setFilterEdge,
  showNode,
}) {
  return (
    <Button
      unstyled
      className="h-7 truncate bg-muted p-0 text-sm font-normal text-black hover:bg-muted"
    >
      <div className="flex">
        <ShadTooltip
          styleClasses={"tooltip-fixed-width custom-scroll nowheel"}
          delayDuration={1000}
          content={
            <HandleTooltips
              left={left}
              nodes={nodes}
              tooltipTitle={tooltipTitle!}
            />
          }
          side={left ? "left" : "right"}
        >
          <div>
            <Handle
              data-test-id={`handle-${title.toLowerCase()}-${
                !showNode
                  ? left
                    ? "target"
                    : "source"
                  : left
                    ? "left"
                    : "right"
              }`}
              type={left ? "target" : "source"}
              position={left ? Position.Left : Position.Right}
              key={scapedJSONStringfy(proxy ? { ...id, proxy } : id)}
              id={scapedJSONStringfy(proxy ? { ...id, proxy } : id)}
              isValidConnection={(connection) =>
                isValidConnection(connection, nodes, edges)
              }
              className={classNames(
                left ? "-ml-1" : "-mr-1",
                "z-20 h-4 w-4 rounded-full border-none bg-background",
              )}
              style={{
                background:
                  "conic-gradient(" +
                  colors
                    .map(
                      (color, index) =>
                        color +
                        " " +
                        (360 / colors.length) * index +
                        "deg " +
                        (360 / colors.length) * (index + 1) +
                        "deg",
                    )
                    .join(" ,") +
                  ")",
                WebkitMaskImage: "radial-gradient(transparent 40%, black 44%)",
                maskImage: "radial-gradient(transparent 40%, black 44%)",
              }}
              onClick={() => {
                setFilterEdge(
                  groupByFamily(myData, tooltipTitle!, left, nodes!),
                );
              }}
            />
            <div
              className={cn(
                "absolute top-[50%] z-10 h-4 w-4 translate-y-[-50%] rounded-full bg-background",
                left ? "-left-[4px] -ml-1" : "-right-[4px] -mr-1",
              )}
            />
          </div>
        </ShadTooltip>
      </div>
    </Button>
  );
}
