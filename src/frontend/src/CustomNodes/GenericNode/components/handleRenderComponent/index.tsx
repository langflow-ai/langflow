import { useDarkStore } from "@/stores/darkStore";
import useFlowStore from "@/stores/flowStore";
import { useMemo, useState } from "react";
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

  const myId = useMemo(
    () => scapedJSONStringfy(proxy ? { ...id, proxy } : id),
    [id, proxy],
  );

  const getConnection = useMemo(
    () =>
      (semiConnection: {
        source: string | undefined;
        sourceHandle: string | undefined;
        target: string | undefined;
        targetHandle: string | undefined;
      }) => ({
        source: semiConnection.source ?? nodeId,
        sourceHandle: semiConnection.sourceHandle ?? myId,
        target: semiConnection.target ?? nodeId,
        targetHandle: semiConnection.targetHandle ?? myId,
      }),
    [nodeId, myId],
  );

  const sameDraggingNode = useMemo(
    () => (!left ? handleDragging?.target : handleDragging?.source) === nodeId,
    [left, handleDragging, nodeId],
  );

  const ownDraggingHandle = useMemo(
    () =>
      handleDragging &&
      (left ? handleDragging?.target : handleDragging?.source) &&
      (left ? handleDragging.targetHandle : handleDragging.sourceHandle) ===
        myId,
    [handleDragging, left, myId],
  );

  const sameFilterNode = useMemo(
    () => (!left ? filterType?.target : filterType?.source) === nodeId,
    [left, filterType, nodeId],
  );

  const ownFilterHandle = useMemo(
    () =>
      filterType &&
      (left ? filterType?.target : filterType?.source) === nodeId &&
      (left ? filterType.targetHandle : filterType.sourceHandle) === myId,
    [filterType, left, myId],
  );

  const sameNode = useMemo(
    () => sameDraggingNode || sameFilterNode,
    [sameDraggingNode, sameFilterNode],
  );
  const ownHandle = useMemo(
    () => ownDraggingHandle || ownFilterHandle,
    [ownDraggingHandle, ownFilterHandle],
  );

  const draggingOpenHandle = useMemo(
    () =>
      handleDragging &&
      (left ? handleDragging.source : handleDragging.target) &&
      !ownDraggingHandle
        ? isValidConnection(getConnection(handleDragging), nodes, edges)
        : false,
    [handleDragging, left, ownDraggingHandle, getConnection, nodes, edges],
  );

  const filterOpenHandle = useMemo(
    () =>
      filterType &&
      (left ? filterType.source : filterType.target) &&
      !ownFilterHandle
        ? isValidConnection(getConnection(filterType), nodes, edges)
        : false,
    [filterType, left, ownFilterHandle, getConnection, nodes, edges],
  );

  const openHandle = useMemo(
    () => filterOpenHandle || draggingOpenHandle,
    [filterOpenHandle, draggingOpenHandle],
  );
  const filterPresent = useMemo(
    () => handleDragging || filterType,
    [handleDragging, filterType],
  );

  const currentFilter = useMemo(
    () =>
      left
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
          },
    [left, myId, nodeId, tooltipTitle, colors],
  );

  const handleColor = useMemo(
    () =>
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
          ")",
    [filterPresent, openHandle, ownHandle, dark, colors],
  );

  const [openTooltip, setOpenTooltip] = useState(false);
  return (
    <div>
      <ShadTooltip
        open={openTooltip}
        setOpen={setOpenTooltip}
        styleClasses={"tooltip-fixed-width custom-scroll nowheel"}
        delayDuration={1000}
        content={
          <HandleTooltipComponent
            isInput={left}
            colors={colors}
            tooltipTitle={tooltipTitle}
            isConnecting={!!filterPresent && !ownHandle}
            isCompatible={openHandle}
            isSameNode={sameNode && !ownHandle}
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
          onMouseUp={() => {
            setOpenTooltip(false);
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
            data-testid={`gradient-handle-${testIdComplement}-${title.toLowerCase()}-${
              !showNode ? (left ? "target" : "source") : left ? "left" : "right"
            }`}
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
