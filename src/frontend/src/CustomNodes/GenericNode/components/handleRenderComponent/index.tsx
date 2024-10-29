import { useDarkStore } from "@/stores/darkStore";
import useFlowStore from "@/stores/flowStore";
import { log } from "console";
import { useEffect, useMemo, useRef, useState } from "react";
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

  const isNullHandle = filterPresent && !(openHandle || ownHandle);

  const handleColor = useMemo(
    () =>
      isNullHandle
        ? dark
          ? "conic-gradient(#27272a 0deg 360deg)"
          : "conic-gradient(#f4f4f5 0deg 360deg)"
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

  const [isHovered, setIsHovered] = useState(false);
  const [openTooltip, setOpenTooltip] = useState(false);

  useEffect(() => {
    if ((isHovered || openHandle) && !isNullHandle) {
      const styleSheet = document.createElement("style");
      styleSheet.id = `pulse-${nodeId}`;
      styleSheet.textContent = `
        @keyframes pulseNeon {
          0% {
            box-shadow: 0 0 0 1px #fff,
                        0 0 2px ${colors[0]},
                        0 0 4px ${colors[0]},
                        0 0 6px ${colors[0]},
                        0 0 8px ${colors[0]},
                        0 0 10px ${colors[0]},
                        0 0 15px ${colors[0]},
                        0 0 20px ${colors[0]};
          }
          50% {
            box-shadow: 0 0 0 1px #fff,
                        0 0 4px ${colors[0]},
                        0 0 8px ${colors[0]},
                        0 0 12px ${colors[0]},
                        0 0 16px ${colors[0]},
                        0 0 20px ${colors[0]},
                        0 0 25px ${colors[0]},
                        0 0 30px ${colors[0]};
          }
          100% {
            box-shadow: 0 0 0 1px #fff,
                        0 0 2px ${colors[0]},
                        0 0 4px ${colors[0]},
                        0 0 6px ${colors[0]},
                        0 0 8px ${colors[0]},
                        0 0 10px ${colors[0]},
                        0 0 15px ${colors[0]},
                        0 0 20px ${colors[0]};
          }
        }
      `;
      document.head.appendChild(styleSheet);
    }

    // Cleanup function should always be returned
    return () => {
      const existingStyle = document.getElementById(`pulse-${nodeId}`);
      if (existingStyle) {
        existingStyle.remove();
      }
    };
  }, [isHovered, openHandle, isNullHandle, colors, nodeId]);

  const getNeonShadow = (color: string, isHovered: boolean) => {
    if (isNullHandle) return "none";
    if (!isHovered && !openHandle) return "none";
    return [
      "0 0 0 1px #fff",
      `0 0 2px ${color}`,
      `0 0 4px ${color}`,
      `0 0 6px ${color}`,
      `0 0 8px ${color}`,
      `0 0 10px ${color}`,
      `0 0 15px ${color}`,
      `0 0 20px ${color}`,
    ].join(", ");
  };

  const handleRef = useRef<HTMLDivElement>(null);
  const invisibleDivRef = useRef<HTMLDivElement>(null);

  return (
    <div>
      <ShadTooltip
        open={openTooltip}
        setOpen={setOpenTooltip}
        styleClasses="tooltip-fixed-width custom-scroll nowheel bottom-2 relative"
        delayDuration={1000}
        contrastTooltip
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
        side="top"
      >
        <div className="relative">
          <Handle
            ref={handleRef}
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
              `group/handle z-50 h-12 w-12 rounded-full border-none bg-transparent transition-all`,
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
            style={{
              background: handleColor,
              width: isHovered ? "18px" : "12px",
              height: isHovered ? "18px" : "12px",
              transition: "all 0.2s",
              boxShadow: getNeonShadow(colors[0], isHovered || openHandle),
              animation:
                (isHovered || openHandle) && !isNullHandle
                  ? "pulseNeon 0.7s ease-in-out infinite"
                  : "none",
              border: isNullHandle ? "1px solid #fff" : "none",
            }}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
          />
          <div
            ref={invisibleDivRef}
            className={cn(
              "noflow nowheel nopan noselect absolute -right-6 -translate-y-1/2 translate-x-1/3 cursor-crosshair rounded-full",
              left && "-left-5 -translate-x-1/2",
            )}
            style={{
              width: "26px",
              height: "26px",
              top: "50%",
              position: "absolute",
              zIndex: 30,
            }}
            onClick={(e) => {
              handleRef.current?.dispatchEvent(
                new MouseEvent("mousedown", { bubbles: true }),
              );
              e.stopPropagation();
              e.preventDefault();
            }}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            onContextMenu={(event) => {
              event.preventDefault();
            }}
          />
        </div>
      </ShadTooltip>
    </div>
  );
}
