import ForwardedIconComponent from "@/components/genericIconComponent";
import useFlowStore from "@/stores/flowStore";
import { Handle, Position } from "reactflow";
import ShadTooltip from "../../../../components/shadTooltipComponent";
import {
  isValidConnection,
  scapedJSONStringfy,
} from "../../../../utils/reactflowUtils";
import { classNames, cn, groupByFamily } from "../../../../utils/utils";

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
  nodeId,
}: {
  left: boolean;
  nodes: any;
  tooltipTitle?: string;
  proxy?: any;
  id: any;
  title: string;
  edges: any;
  myData: any;
  colors: string[];
  setFilterEdge: any;
  showNode: any;
  testIdComplement?: string;
  nodeId: string;
}) {
  const setHandleDragging = useFlowStore((state) => state.setHandleDragging);
  const setFilterType = useFlowStore((state) => state.setFilterType);
  const handleDragging = useFlowStore((state) => state.handleDragging);
  const filterType = useFlowStore((state) => state.filterType);

  const onConnect = useFlowStore((state) => state.onConnect);

  const handleMouseUp = () => {
    setHandleDragging(undefined);
    document.removeEventListener("mouseup", handleMouseUp);
  };

  const myId = scapedJSONStringfy(proxy ? { ...id, proxy } : id);

  const ownDraggingHandle =
    handleDragging &&
    (left ? handleDragging.target : handleDragging.source) === nodeId &&
    (left ? handleDragging.targetHandle : handleDragging.sourceHandle) === myId;
  const ownFilterHandle =
    filterType &&
    (left ? filterType.target : filterType.source) === nodeId &&
    (left ? filterType.targetHandle : filterType.sourceHandle) === myId;

  const ownHandle = ownDraggingHandle || ownFilterHandle;

  const draggingOpenHandle =
    handleDragging &&
    (left ? handleDragging.source : handleDragging.target) &&
    !ownDraggingHandle
      ? isValidConnection(
          {
            source: handleDragging.source ?? nodeId,
            sourceHandle: handleDragging.sourceHandle ?? myId,
            target: handleDragging.target ?? nodeId,
            targetHandle: handleDragging.targetHandle ?? myId,
          },
          nodes,
          edges,
        )
      : false;

  const filterOpenHandle =
    filterType &&
    (left ? filterType.source : filterType.target) &&
    !ownFilterHandle
      ? isValidConnection(
          {
            source: filterType.source ?? nodeId,
            sourceHandle: filterType.sourceHandle ?? myId,
            target: filterType.target ?? nodeId,
            targetHandle: filterType.targetHandle ?? myId,
          },
          nodes,
          edges,
        )
      : false;

  const openHandle = filterOpenHandle || draggingOpenHandle;

  return (
    <div>
      <ShadTooltip
        styleClasses={"tooltip-fixed-width custom-scroll nowheel"}
        delayDuration={1000}
        content={
          <div className="py-1.5 text-xs">
            <span className="mr-1">Type: </span>
            <span
              className="rounded-md px-2 pb-1 pt-0.5 text-background"
              style={{ backgroundColor: colors[0] }}
            >
              {tooltipTitle}
            </span>
          </div>
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
            `group/handle z-20 rounded-full border-none transition-all`,

            handleDragging || filterType
              ? openHandle || ownHandle
                ? cn(left ? "-ml-[8.5px]" : "-mr-[8.5px]", "!h-6 !w-6")
                : cn("h-1.5 w-1.5", left ? "ml-[0.5px]" : "mr-[0.5px]")
              : cn(
                  left
                    ? "group-hover/node:-ml-[8.5px]"
                    : "group-hover/node:-mr-[8.5px]",
                  "h-1.5 w-1.5 group-hover/node:h-6 group-hover/node:w-6",
                  left ? "ml-[0.5px]" : "mr-[0.5px]",
                ),
          )}
          style={{
            background:
              (handleDragging || filterType) && !(openHandle || ownHandle)
                ? "conic-gradient(gray 0deg 360deg)"
                : "conic-gradient(" +
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
          }}
          onClick={() => {
            setFilterEdge(groupByFamily(myData, tooltipTitle!, left, nodes!));
            setFilterType(
              left
                ? {
                    targetHandle: myId,
                    target: nodeId,
                    source: undefined,
                    sourceHandle: undefined,
                  }
                : {
                    sourceHandle: myId,
                    source: nodeId,
                    target: undefined,
                    targetHandle: undefined,
                  },
            );
            if (filterOpenHandle && filterType) {
              onConnect({
                source: filterType.source ?? nodeId,
                sourceHandle: filterType.sourceHandle ?? myId,
                target: filterType.target ?? nodeId,
                targetHandle: filterType.targetHandle ?? myId,
              });
              setFilterType(undefined);
            }
          }}
          onMouseDown={() => {
            setHandleDragging(
              left
                ? {
                    targetHandle: myId,
                    target: nodeId,
                    source: undefined,
                    sourceHandle: undefined,
                  }
                : {
                    sourceHandle: myId,
                    source: nodeId,
                    target: undefined,
                    targetHandle: undefined,
                  },
            );
            document.addEventListener("mouseup", handleMouseUp);
          }}
          onMouseUp={() => {
            console.log("parou");
            setHandleDragging(undefined);
          }}
        >
          <div
            className={cn(
              "pointer-events-none absolute top-[50%] z-30 flex h-0 w-0 translate-y-[-50%] items-center justify-center rounded-full bg-transparent transition-all group-hover/handle:bg-transparent",
              left
                ? "left-[5.5px] group-hover/node:left-0.5"
                : "right-[5.5px] group-hover/node:right-0.5",
              handleDragging || filterType
                ? openHandle || ownHandle
                  ? cn(
                      left ? "left-0.5" : "right-0.5",
                      "h-5 w-5",
                      ownHandle
                        ? "bg-transparent"
                        : "bg-background group-hover/handle:bg-transparent",
                    )
                  : ""
                : "group-hover/node:h-5 group-hover/node:w-5 group-hover/node:bg-background",
            )}
          >
            <ForwardedIconComponent
              iconColor={colors[0]}
              name="Plus"
              className={cn(
                "h-4 w-4 scale-0 transition-all",
                handleDragging || filterType
                  ? openHandle || ownHandle
                    ? cn(
                        ownHandle
                          ? "text-background"
                          : "group-hover/handle:text-background",
                        "scale-100",
                      )
                    : ""
                  : "group-hover/node:scale-100 group-hover/handle:text-background",
              )}
            />
          </div>
        </Handle>
      </ShadTooltip>
      <div
        className={cn(
          "pointer-events-none absolute top-[50%] z-10 flex h-3 w-3 translate-y-[-50%] items-center justify-center rounded-full opacity-50 transition-all group-hover/handle:bg-transparent",
          left ? "-left-[6.5px]" : "-right-[6.5px]",
        )}
        style={{
          background:
            (handleDragging || filterType) && !(openHandle || ownHandle)
              ? "conic-gradient(gray 0deg 360deg)"
              : "conic-gradient(" +
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
        }}
      />
    </div>
  );
}
