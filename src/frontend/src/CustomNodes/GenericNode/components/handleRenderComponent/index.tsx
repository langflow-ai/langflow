import { title } from "process";
import { Handle, Position } from "reactflow";
import ShadTooltip from "../../../../components/shadTooltipComponent";
import { Button } from "../../../../components/ui/button";
import {
  isValidConnection,
  scapedJSONStringfy,
} from "../../../../utils/reactflowUtils";
import { classNames, cn, groupByFamily } from "../../../../utils/utils";
import HandleTooltips from "../HandleTooltipComponent";

export default function HandleRenderComponent({
  left,
  nodes,
  tooltipTitle = "",
  proxy,
  id,
  title,
  edges,
  myData,
  colors,
  setFilterEdge,
  showNode,
  testIdComplement,
}: {
  left: boolean;
  nodes: any;
  tooltipTitle?: string;
  proxy: any;
  id: any;
  title: string;
  edges: any;
  myData: any;
  colors: string[];
  setFilterEdge: any;
  showNode: any;
  testIdComplement?: string;
}) {
  return (
    <Button
      unstyled
      className="h-7 truncate bg-muted p-0 text-sm font-normal text-black hover:bg-muted"
    >
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
        <Handle
          data-testid={`handle-${testIdComplement}-${title.toLowerCase()}-${
            !showNode ? (left ? "target" : "source") : left ? "left" : "right"
          }`}
          type={left ? "target" : "source"}
          position={left ? Position.Left : Position.Right}
          key={scapedJSONStringfy(proxy ? { ...id, proxy } : id)}
          id={scapedJSONStringfy(proxy ? { ...id, proxy } : id)}
          isValidConnection={(connection) =>
            isValidConnection(connection, nodes, edges)
          }
          className={classNames(
            left ? "-ml-0.5" : "-mr-0.5",
            "z-20 h-3 w-3 rounded-full border-none bg-background",
          )}
          style={{
            background:
              "conic-gradient(" +
              colors
                .concat(colors[0])
                .map(
                  (color, index) =>
                    color +
                    " " +
                    ((360 / colors.length) * index -
                      360 / (colors.length * 4)) +
                    "deg " +
                    ((360 / colors.length) * index +
                      360 / (colors.length * 4)) +
                    "deg",
                )
                .join(" ,") +
              ")",
            WebkitMaskImage: "radial-gradient(transparent 40%, black 44%)",
            maskImage: "radial-gradient(transparent 40%, black 44%)",
          }}
          onClick={() => {
            setFilterEdge(groupByFamily(myData, tooltipTitle!, left, nodes!));
          }}
        />
      </ShadTooltip>
      <div
        className={cn(
          "absolute top-[50%] z-10 h-3 w-3 translate-y-[-50%] rounded-full bg-background",
          left ? "-left-[4px] -ml-0.5" : "-right-[4px] -mr-0.5",
        )}
      />
    </Button>
  );
}
