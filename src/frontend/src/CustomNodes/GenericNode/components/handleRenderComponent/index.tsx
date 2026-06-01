import { type Connection, Handle, Position } from "@xyflow/react";
import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import { useDarkStore } from "@/stores/darkStore";
import useFlowStore from "@/stores/flowStore";
import type { NodeDataType } from "@/types/flow";
import { nodeColorsName } from "@/utils/styleUtils";
import ShadTooltip from "../../../../components/common/shadTooltipComponent";
import {
  isValidConnection,
  scapedJSONStringfy,
} from "../../../../utils/reactflowUtils";
import { cn, groupByFamily } from "../../../../utils/utils";
import HandleTooltipComponent from "../HandleTooltipComponent";
import { isInputHandleCollapsed } from "./inputHandleVisibility";

// Resting size of an input handle dot when it is not revealed, vs. its full
// size when hovered/selected/connected/connecting.
const COLLAPSED_HANDLE_SIZE = "5px";
const EXPANDED_HANDLE_SIZE = "10px";

const BASE_HANDLE_STYLES = {
  width: "32px",
  height: "32px",
  top: "50%",
  position: "absolute" as const,
  zIndex: 30,
  background: "transparent",
  border: "none",
} as const;

const HandleContent = memo(function HandleContent({
  isNullHandle,
  handleColor,
  accentForegroundColorName,
  isHovered,
  openHandle,
  selected,
  hasConnectedEdge,
  filterPresent,
  isInConnectionMode,
  testIdComplement,
  title,
  showNode,
  left,
  nodeId,
}: {
  isNullHandle: boolean;
  handleColor: string;
  accentForegroundColorName: string;
  isHovered: boolean;
  openHandle: boolean;
  selected: boolean;
  hasConnectedEdge: boolean;
  filterPresent: boolean;
  isInConnectionMode: boolean;
  testIdComplement?: string;
  title: string;
  showNode: boolean;
  left: boolean;
  nodeId: string;
}) {
  // Restore animation effect
  useEffect(() => {
    if ((isHovered || openHandle) && !isNullHandle) {
      const styleSheet = document.createElement("style");
      styleSheet.id = `pulse-${nodeId}`;
      styleSheet.textContent = `
        @keyframes pulseNeon-${nodeId} {
          0% {
            box-shadow: 0 0 0 3px hsl(var(--node-ring)),
                        0 0 2px ${handleColor},
                        0 0 4px ${handleColor},
                        0 0 6px ${handleColor},
                        0 0 8px ${handleColor},
                        0 0 10px ${handleColor},
                        0 0 15px ${handleColor},
                        0 0 20px ${handleColor};
          }
          50% {
            box-shadow: 0 0 0 3px hsl(var(--node-ring)),
                        0 0 4px ${handleColor},
                        0 0 8px ${handleColor},
                        0 0 12px ${handleColor},
                        0 0 16px ${handleColor},
                        0 0 20px ${handleColor},
                        0 0 25px ${handleColor},
                        0 0 30px ${handleColor};
          }
          100% {
            box-shadow: 0 0 0 3px hsl(var(--node-ring)),
                        0 0 2px ${handleColor},
                        0 0 4px ${handleColor},
                        0 0 6px ${handleColor},
                        0 0 8px ${handleColor},
                        0 0 10px ${handleColor},
                        0 0 15px ${handleColor},
                        0 0 20px ${handleColor};
          }
        }
      `;
      document.head.appendChild(styleSheet);

      return () => {
        const existingStyle = document.getElementById(`pulse-${nodeId}`);
        if (existingStyle) {
          existingStyle.remove();
        }
      };
    }
  }, [isHovered, openHandle, isNullHandle, nodeId, handleColor]);

  const getNeonShadow = useCallback(
    (color: string, isActive: boolean) => {
      if (isNullHandle) return "none";
      if (!isActive) return `0 0 0 3px ${color}`;
      return [
        "0 0 0 1px hsl(var(--border))",
        `0 0 2px ${color}`,
        `0 0 4px ${color}`,
        `0 0 6px ${color}`,
        `0 0 8px ${color}`,
        `0 0 10px ${color}`,
        `0 0 15px ${color}`,
        `0 0 20px ${color}`,
      ].join(", ");
    },
    [isNullHandle],
  );

  // Input handles render as a small collapsed dot by default and grow to full
  // size when hovered, when the node is selected, when connected, or while a
  // connection drag/filter is active. Null handles always render at full size
  // (grayed) so an in-progress drag can show incompatible targets.
  const isCollapsed = useMemo(
    () =>
      !isNullHandle &&
      isInputHandleCollapsed({
        left,
        isHovered,
        selected,
        hasConnectedEdge,
        filterPresent,
        isInConnectionMode,
      }),
    [
      isNullHandle,
      left,
      isHovered,
      selected,
      hasConnectedEdge,
      filterPresent,
      isInConnectionMode,
    ],
  );

  const contentStyle = useMemo(() => {
    const dotSize = isCollapsed ? COLLAPSED_HANDLE_SIZE : EXPANDED_HANDLE_SIZE;
    // A collapsed input handle wears the same colorless (gray) look as a
    // null/incompatible handle — only revealed handles show their datatype
    // color and glow.
    const usesInactiveAppearance = isNullHandle || isCollapsed;
    return {
      background: usesInactiveAppearance ? "hsl(var(--border))" : handleColor,
      width: dotSize,
      height: dotSize,
      transition: "all 0.2s",
      opacity: 1,
      boxShadow: usesInactiveAppearance
        ? "none"
        : getNeonShadow(accentForegroundColorName, isHovered || openHandle),
      animation:
        (isHovered || openHandle) && !isNullHandle
          ? `pulseNeon-${nodeId} 1.1s ease-in-out infinite`
          : "none",
      border: usesInactiveAppearance ? "2px solid hsl(var(--muted))" : "none",
    };
  }, [
    isNullHandle,
    isCollapsed,
    handleColor,
    getNeonShadow,
    accentForegroundColorName,
    isHovered,
    openHandle,
    nodeId,
  ]);

  return (
    <div
      data-testid={`div-handle-${testIdComplement}-${title.toLowerCase()}-${
        !showNode ? (left ? "target" : "source") : left ? "left" : "right"
      }`}
      className="noflow nowheel nopan noselect pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 cursor-crosshair rounded-full"
      style={contentStyle}
    />
  );
});

const HandleRenderComponent = memo(function HandleRenderComponent({
  left,
  tooltipTitle = "",
  proxy,
  id,
  title,
  myData,
  colors,
  setFilterEdge,
  showNode,
  testIdComplement,
  nodeId,
  colorName,
  selected = false,
}: {
  left: boolean;
  tooltipTitle?: string;
  proxy?: any;
  id: any;
  title: string;
  myData: any;
  colors: string[];
  setFilterEdge: (edges: any) => void;
  showNode: boolean;
  testIdComplement?: string;
  nodeId: string;
  colorName?: string[];
  selected?: boolean;
}) {
  const [isHovered, setIsHovered] = useState(false);
  const [openTooltip, setOpenTooltip] = useState(false);

  const isLocked = useFlowStore(
    useShallow((state) => state.currentFlow?.locked),
  );

  const edges = useFlowStore((state) => state.edges);

  // Check if this node is in "connect other models" mode
  const isInConnectionMode = useFlowStore(
    useCallback(
      (state) => {
        if (id?.type !== "model" || !left) return false;
        const node = state.nodes.find((n) => n.id === nodeId);
        return (node?.data as NodeDataType)?._connectionMode === true;
      },
      [nodeId, id?.type, left],
    ),
  );

  const {
    setHandleDragging,
    setFilterType,
    setFilterComponent,
    handleDragging,
    filterType,
    onConnect,
  } = useFlowStore(
    useCallback(
      (state) => ({
        setHandleDragging: state.setHandleDragging,
        setFilterType: state.setFilterType,
        setFilterComponent: state.setFilterComponent,
        handleDragging: state.handleDragging,
        filterType: state.filterType,
        onConnect: state.onConnect,
      }),
      [],
    ),
  );

  const dark = useDarkStore((state) => state.dark);

  const myId = useMemo(
    () => scapedJSONStringfy(proxy ? { ...id, proxy } : id),
    [id, proxy],
  );

  const getConnection = (semiConnection: {
    source?: string;
    sourceHandle?: string;
    target?: string;
    targetHandle?: string;
  }) => ({
    source: semiConnection.source ?? nodeId,
    sourceHandle: semiConnection.sourceHandle ?? myId,
    target: semiConnection.target ?? nodeId,
    targetHandle: semiConnection.targetHandle ?? myId,
  });

  const {
    sameNode,
    ownHandle,
    openHandle,
    filterOpenHandle,
    filterPresent,
    currentFilter,
    isNullHandle,
    hasConnectedEdge,
    handleColor,
    accentForegroundColorName,
  } = useMemo(() => {
    const sameDraggingNode =
      (!left ? handleDragging?.target : handleDragging?.source) === nodeId;
    const sameFilterNode =
      (!left ? filterType?.target : filterType?.source) === nodeId;

    const ownDraggingHandle =
      handleDragging &&
      (left ? handleDragging?.target : handleDragging?.source) &&
      (left ? handleDragging.targetHandle : handleDragging.sourceHandle) ===
        myId;

    const ownFilterHandle =
      filterType &&
      (left ? filterType?.target : filterType?.source) === nodeId &&
      (left ? filterType.targetHandle : filterType.sourceHandle) === myId;

    const draggingOpenHandle =
      handleDragging &&
      (left ? handleDragging.source : handleDragging.target) &&
      !ownDraggingHandle
        ? isValidConnection(getConnection(handleDragging))
        : false;

    const filterOpenHandle =
      filterType &&
      (left ? filterType.source : filterType.target) &&
      !ownFilterHandle
        ? isValidConnection(getConnection(filterType))
        : false;

    const openHandle = filterOpenHandle || draggingOpenHandle;
    const filterPresent = handleDragging || filterType;

    const connectedEdge = edges.find(
      (edge) => edge.target === nodeId && edge.targetHandle === myId,
    );
    const outputType = connectedEdge?.data?.sourceHandle?.output_types?.[0];
    const connectedColor = (outputType && nodeColorsName[outputType]) || "gray";

    // Model handles that initiated connection mode on this node should not be nulled
    const isOwnModelConnectionMode =
      id?.type === "model" && left && filterType?.target === nodeId;

    const isNullHandle =
      filterPresent &&
      !(
        openHandle ||
        ownDraggingHandle ||
        ownFilterHandle ||
        isOwnModelConnectionMode
      );

    // Create a Set from colorName to remove duplicates
    const colorNameSet = new Set(colorName || []);
    const uniqueColorCount = colorNameSet.size;
    const firstUniqueColor =
      colorName && colorName.length > 0 ? colorName[0] : "";

    const handleColorName = connectedEdge
      ? connectedColor
      : uniqueColorCount > 1
        ? "secondary-foreground"
        : "datatype-" + firstUniqueColor;

    const handleColor = isNullHandle
      ? dark
        ? "hsl(var(--accent-gray))"
        : "hsl(var(--accent-gray-foreground)"
      : connectedEdge
        ? "hsl(var(--datatype-" + connectedColor + "))"
        : uniqueColorCount > 1
          ? "hsl(var(--secondary-foreground))"
          : "hsl(var(--datatype-" + firstUniqueColor + "))";

    const accentForegroundColorName = connectedEdge
      ? "hsl(var(--datatype-" + connectedColor + "-foreground))"
      : uniqueColorCount > 1
        ? "hsl(var(--input))"
        : "hsl(var(--datatype-" + firstUniqueColor + "-foreground))";

    const currentFilter = left
      ? {
          targetHandle: myId,
          target: nodeId,
          source: undefined,
          sourceHandle: undefined,
          type: tooltipTitle,
          color: handleColorName,
        }
      : {
          sourceHandle: myId,
          source: nodeId,
          target: undefined,
          targetHandle: undefined,
          type: tooltipTitle,
          color: handleColorName,
        };

    return {
      sameNode: sameDraggingNode || sameFilterNode,
      ownHandle: ownDraggingHandle || ownFilterHandle,
      accentForegroundColorName,
      openHandle,
      filterOpenHandle,
      filterPresent,
      currentFilter,
      isNullHandle,
      hasConnectedEdge: !!connectedEdge,
      handleColor,
    };
  }, [
    left,
    handleDragging,
    filterType,
    nodeId,
    myId,
    dark,
    colors,
    colorName,
    tooltipTitle,
    edges,
    id,
    isInConnectionMode,
  ]);

  const handleMouseDown = useCallback(
    (event: React.MouseEvent) => {
      if (event.button === 0) {
        setHandleDragging(currentFilter);
        const handleMouseUp = () => {
          setHandleDragging(undefined);
          document.removeEventListener("mouseup", handleMouseUp);
        };
        document.addEventListener("mouseup", handleMouseUp);
      }
    },
    [currentFilter, setHandleDragging],
  );

  const handleClick = useCallback(() => {
    const nodes = useFlowStore.getState().nodes;
    setFilterEdge(groupByFamily(myData, tooltipTitle!, left, nodes!));
    setFilterType(currentFilter);
    setFilterComponent("");
    if (filterOpenHandle && filterType) {
      onConnect(getConnection(filterType));
      setFilterType(undefined);
      setFilterEdge([]);
      setFilterComponent("");
    }
  }, [
    myData,
    tooltipTitle,
    left,
    setFilterEdge,
    setFilterType,
    setFilterComponent,
    currentFilter,
    filterOpenHandle,
    filterType,
    onConnect,
  ]);

  const handleMouseEnter = useCallback(() => setIsHovered(true), []);
  const handleMouseLeave = useCallback(() => setIsHovered(false), []);
  const handleMouseUp = useCallback(() => setOpenTooltip(false), []);
  const handleContextMenu = useCallback(
    (e: React.MouseEvent) => e.preventDefault(),
    [],
  );

  return (
    <div>
      <ShadTooltip
        open={openTooltip && !isLocked}
        setOpen={setOpenTooltip}
        styleClasses={cn("tooltip-fixed-width custom-scroll nowheel bottom-2")}
        delayDuration={1000}
        content={
          <HandleTooltipComponent
            isInput={left}
            tooltipTitle={tooltipTitle}
            isConnecting={!!filterPresent && !ownHandle}
            isCompatible={openHandle}
            isSameNode={sameNode && !ownHandle}
            left={left}
          />
        }
        side={left ? "left" : "right"}
      >
        <Handle
          type={left ? "target" : "source"}
          position={left ? Position.Left : Position.Right}
          id={myId}
          isValidConnection={(connection) =>
            isLocked ? false : isValidConnection(connection as Connection)
          }
          className={cn(
            `group/handle z-50 transition-all`,
            !showNode && "no-show",
          )}
          style={{
            ...BASE_HANDLE_STYLES,
            pointerEvents: isLocked ? "none" : "auto",
          }}
          onClick={handleClick}
          onMouseUp={handleMouseUp}
          onContextMenu={handleContextMenu}
          onMouseDown={handleMouseDown}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          data-testid={`handle-${testIdComplement}-${title.toLowerCase()}-${
            !showNode ? (left ? "target" : "source") : left ? "left" : "right"
          }`}
        >
          <HandleContent
            isNullHandle={isNullHandle ?? false}
            handleColor={handleColor}
            accentForegroundColorName={accentForegroundColorName}
            isHovered={isHovered}
            openHandle={openHandle}
            selected={selected}
            hasConnectedEdge={hasConnectedEdge ?? false}
            filterPresent={!!filterPresent}
            isInConnectionMode={isInConnectionMode}
            testIdComplement={testIdComplement}
            title={title}
            showNode={showNode}
            left={left}
            nodeId={nodeId}
          />
        </Handle>
      </ShadTooltip>
    </div>
  );
});

export default HandleRenderComponent;
