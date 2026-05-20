import {
  BaseEdge,
  EdgeLabelRenderer,
  type EdgeProps,
  getBezierPath,
  Position,
} from "@xyflow/react";
import { memo, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import useFlowStore from "@/stores/flowStore";
import { scapeJSONParse } from "@/utils/reactflowUtils";

const UNRECOGNIZED_DOM_PROPS = [
  "targetPosition",
  "sourcePosition",
  "pathOptions",
];

const getCubicBezierPoint = (
  sourceX: number,
  sourceY: number,
  sourceControlX: number,
  sourceControlY: number,
  targetControlX: number,
  targetControlY: number,
  targetX: number,
  targetY: number,
) => {
  const midpoint = 0.5;
  const inverseMidpoint = 1 - midpoint;

  return {
    x:
      inverseMidpoint ** 3 * sourceX +
      3 * inverseMidpoint ** 2 * midpoint * sourceControlX +
      3 * inverseMidpoint * midpoint ** 2 * targetControlX +
      midpoint ** 3 * targetX,
    y:
      inverseMidpoint ** 3 * sourceY +
      3 * inverseMidpoint ** 2 * midpoint * sourceControlY +
      3 * inverseMidpoint * midpoint ** 2 * targetControlY +
      midpoint ** 3 * targetY,
  };
};

export const DefaultEdge = memo(function DefaultEdge({
  sourceHandleId,
  source,
  sourceX,
  sourceY,
  target,
  targetHandleId,
  targetX,
  targetY,
  id,
  ...props
}: EdgeProps) {
  const [isHovered, setIsHovered] = useState(false);
  const getNode = useFlowStore((state) => state.getNode);
  const deleteEdge = useFlowStore((state) => state.deleteEdge);

  const sourceNode = getNode(source);
  const targetNode = getNode(target);

  const targetHandleObject = scapeJSONParse(targetHandleId!);

  const sourceXNew =
    (sourceNode?.position.x ?? 0) + (sourceNode?.measured?.width ?? 0) + 7;
  const targetXNew = (targetNode?.position.x ?? 0) - 7;

  const distance = 200 + 0.1 * ((sourceXNew - targetXNew) / 2);

  const zeroOnNegative =
    (1 +
      (1 - Math.exp(-0.01 * Math.abs(sourceXNew - targetXNew))) *
        (sourceXNew - targetXNew >= 0 ? 1 : -1)) /
    2;

  const distanceY =
    200 -
    200 * (1 - zeroOnNegative) +
    0.3 * Math.abs(targetY - sourceY) * zeroOnNegative;

  const sourceDistanceY =
    200 -
    200 * (1 - zeroOnNegative) +
    0.3 * Math.abs(sourceY - targetY) * zeroOnNegative;

  const targetYNew = targetY + 1;
  const sourceYNew = sourceY + 1;

  const edgePathLoop = `M ${sourceXNew} ${sourceYNew} C ${sourceXNew + distance} ${sourceYNew + sourceDistanceY}, ${targetXNew - distance} ${targetYNew + distanceY}, ${targetXNew} ${targetYNew}`;

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX: sourceXNew,
    sourceY: sourceYNew,
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    targetX: targetXNew,
    targetY: targetYNew,
  });

  const loopLabelPosition = getCubicBezierPoint(
    sourceXNew,
    sourceYNew,
    sourceXNew + distance,
    sourceYNew + sourceDistanceY,
    targetXNew - distance,
    targetYNew + distanceY,
    targetXNew,
    targetYNew,
  );

  const deleteButtonX = targetHandleObject.output_types
    ? loopLabelPosition.x
    : labelX;
  const deleteButtonY = targetHandleObject.output_types
    ? loopLabelPosition.y
    : labelY;

  const { animated, selectable, deletable, selected, ...domSafeProps } = props;

  //Remove unrecognized DOM props
  UNRECOGNIZED_DOM_PROPS.forEach((prop) => {
    if (prop in domSafeProps) {
      delete domSafeProps[prop];
    }
  });

  return (
    <>
      <BaseEdge
        id={id}
        path={targetHandleObject.output_types ? edgePathLoop : edgePath}
        strokeDasharray={targetHandleObject.output_types ? "5 5" : "0"}
        {...domSafeProps}
        data-animated={animated ? "true" : "false"}
        data-selectable={selectable ? "true" : "false"}
        data-deletable={deletable ? "true" : "false"}
        data-selected={selected ? "true" : "false"}
      />

      {(selected || isHovered) && deletable !== false && (
        <EdgeLabelRenderer>
          <button
            type="button"
            className="nodrag nopan pointer-events-auto absolute flex size-[27px] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-border bg-background text-muted-foreground shadow-sm transition-colors hover:border-destructive hover:bg-destructive hover:text-destructive-foreground"
            style={{
              transform: `translate(-50%, -50%) translate(${deleteButtonX}px, ${deleteButtonY}px)`,
            }}
            aria-label="Delete connection"
            data-testid="edge-delete-button"
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              deleteEdge(id);
            }}
          >
            <IconComponent name="X" className="size-3" />
          </button>
        </EdgeLabelRenderer>
      )}

      <ContextMenu>
        <ContextMenuTrigger asChild>
          <path
            className="react-flow__edge-interaction"
            d={targetHandleObject.output_types ? edgePathLoop : edgePath}
            strokeOpacity={0}
            strokeWidth={20}
            fill="none"
            role="button"
            aria-label="Connection"
            data-testid={`edge-context-menu-trigger`}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
          />
        </ContextMenuTrigger>
        <ContextMenuContent>
          <ContextMenuItem
            variant="destructive"
            onClick={() => {
              deleteEdge(id);
            }}
            data-testid="context-menu-item-destructive"
          >
            <IconComponent name="Trash2" className="size-3.5 text-inherit" />
            <span className="text-xs">Delete</span>
          </ContextMenuItem>
        </ContextMenuContent>
      </ContextMenu>
    </>
  );
});
