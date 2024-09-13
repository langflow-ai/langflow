import { useDarkStore } from "@/stores/darkStore";
import useFlowStore from "@/stores/flowStore";
import { Handle, Position } from "reactflow";
import ShadTooltip from "../../../../components/shadTooltipComponent";
import {
  isValidConnection,
  scapedJSONStringfy,
} from "../../../../utils/reactflowUtils";
import { classNames, cn, groupByFamily } from "../../../../utils/utils";
import HandleTooltipComponent from "../HandleTooltipComponent";

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
  const dark = useDarkStore((state) => state.dark);

  const onConnect = useFlowStore((state) => state.onConnect);

  const handleMouseUp = () => {
    setHandleDragging(undefined);
    document.removeEventListener("mouseup", handleMouseUp);
  };

  const getConnection = (semiConnection: {
    source: string | undefined;
    sourceHandle: string | undefined;
    target: string | undefined;
    targetHandle: string | undefined;
  }) => ({
    source: semiConnection.source ?? nodeId,
    sourceHandle: semiConnection.sourceHandle ?? myId,
    target: semiConnection.target ?? nodeId,
    targetHandle: semiConnection.targetHandle ?? myId,
  });

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
      ? isValidConnection(getConnection(handleDragging), nodes, edges)
      : false;

  const filterOpenHandle =
    filterType &&
    (left ? filterType.source : filterType.target) &&
    !ownFilterHandle
      ? isValidConnection(getConnection(filterType), nodes, edges)
      : false;

  const openHandle = filterOpenHandle || draggingOpenHandle;

  const filterPresent = handleDragging || filterType;

  const currentFilter = left
    ? {
        targetHandle: myId,
        target: nodeId,
        source: undefined,
        sourceHandle: undefined,
        type: tooltipTitle,
        color: colors[0],
      }
    : {
        sourceHandle: myId,
        source: nodeId,
        target: undefined,
        targetHandle: undefined,
        type: tooltipTitle,
        color: colors[0],
      };

  const handleColor =
    filterPresent && !(openHandle || ownHandle)
      ? dark
        ? "conic-gradient(#374151 0deg 360deg)"
        : "conic-gradient(#cbd5e1 0deg 360deg)"
      : "conic-gradient(" +
        colors
          .concat(colors[0])
          .map(
            (color, index) =>
              color +
              " " +
              ((360 / colors.length) * index - 360 / (colors.length * 4)) +
              "deg " +
              ((360 / colors.length) * index + 360 / (colors.length * 4)) +
              "deg",
          )
          .join(" ,") +
        ")";

  return (
    <div>
      <ShadTooltip
        styleClasses={"tooltip-fixed-width custom-scroll nowheel"}
        delayDuration={1000}
        content={
          <HandleTooltipComponent
            isInput={left}
            color={colors[0]}
            tooltipTitle={tooltipTitle}
            isConnecting={!!filterPresent && !ownHandle}
            isCompatible={openHandle}
            isSameNode={
              nodeId === (handleDragging?.target ?? handleDragging?.source)
            }
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
          key={myId}
          id={myId}
          isValidConnection={(connection) =>
            isValidConnection(connection, nodes, edges)
          }
          className={classNames(
            `group/handle z-20 h-6 w-6 rounded-full border-none bg-transparent transition-all`,
          )}
          onClick={() => {
            setFilterEdge(groupByFamily(myData, tooltipTitle!, left, nodes!));
            setFilterType(currentFilter);
            if (filterOpenHandle && filterType) {
              onConnect(getConnection(filterType));
              setFilterType(undefined);
              setFilterEdge([]);
            }
          }}
          onContextMenu={(event) => {
            event.preventDefault();
          }}
          onMouseDown={(event) => {
            if (event.button === 0) {
              setHandleDragging(currentFilter);
              document.addEventListener("mouseup", handleMouseUp);
            }
          }}
        >
          <div
            className={cn(
              "pointer-events-none absolute left-1/2 top-[50%] z-30 flex h-0 w-0 -translate-x-1/2 translate-y-[-50%] items-center justify-center rounded-full bg-background transition-all group-hover/handle:bg-transparent",
              filterPresent
                ? openHandle || ownHandle
                  ? cn(
                      "h-4 w-4",
                      ownHandle ? "bg-transparent" : "bg-background",
                    )
                  : ""
                : "group-hover/node:h-4 group-hover/node:w-4",
            )}
          ></div>
          <div
            className="pointer-events-none absolute left-1/2 top-[50%] z-10 flex h-3 w-3 -translate-x-1/2 translate-y-[-50%] items-center justify-center rounded-full opacity-50 transition-all"
            style={{
              background: handleColor,
            }}
          />
          <div
            className={classNames(
              `pointer-events-none absolute left-1/2 top-[50%] z-10 flex -translate-x-1/2 translate-y-[-50%] items-center justify-center rounded-full transition-all`,
              filterPresent
                ? openHandle || ownHandle
                  ? cn("h-5 w-5")
                  : cn("h-1.5 w-1.5")
                : cn("h-1.5 w-1.5 group-hover/node:h-5 group-hover/node:w-5"),
            )}
            style={{
              background: handleColor,
            }}
          />
        </Handle>
      </ShadTooltip>
    </div>
  );
}
